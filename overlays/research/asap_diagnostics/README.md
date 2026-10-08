# ASAP delta 数据流诊断与服务器重跑协议

核查：2026-10-07；本地 commit `df5320cc47dd8cad97961bdfabfe402dd62ad999`。
这是代码审计、CPU 合约检查和实验协议，没有完成 IsaacGym 物理回放或 RL 训练。
用户附件是研究背景；其中历史聊天的指令没有作为本次操作指令执行。
本次实际验证：补丁可干净应用；四个修改后源码可编译；CPU 张量检查通过；合成连续/重置数据的审计与已知误差回放比较通过。

## 已核实与尚缺证据

- 本地 `logs/SquatL1`、`logs/StepFBL1` 有 `model_6000.pt`、config 和导出 ONNX；未找到 CR7 calibration rollout、delta checkpoint 或上次训练/比较命令。
- 两个 source config 都是 ankle Kp20、action_scale0.25、200 Hz physics / 50 Hz control、self_collisions0、无控制延迟随机化。
- source reference 时长：SquatL1 5.233 s；StepFBL1 3.933 s。保存步数需小于参考末尾或按 episode 分段。
- 不能由“训练1000轮后更差”独立判断数据少、ASAP 无效或具体某个 bug 是唯一原因。

## 三个阶段分别比较什么

令 A 为默认 Gym，B 为 ankle Kp16 的 Gym，π0 为在 A 训练的 motion policy。

1. 采集：在 B 中运行 π0，得到真实执行序列 D_B。
2. 动力学校准：在 A 中回放 D_B 的原始 action，训练 δ 让 A 的状态逼近 D_B 的实际状态。此时参考是 D_B，不是原人体动作。
3. 控制微调：冻结 δ，在 A+δ 中训练 motion policy，参考换回原始 retargeted motion。然后在 B 中执行微调 policy，不注入 δ，比较它和原动作的误差。

开环回放的 nominal action 固定，δ 仍可反馈当前仿真状态。让 π0 每拍重算 action 再比较两条轨迹，不是同输入动力学校准测试。

## 代码审计发现

### 1. 正确的 action 含义与时间轴

`legged_robot_base.py:213` 保存 clipped、未缩放 action；
`motion_tracking.py:485–540` 在父类完成 physics、reward 和 reset 后记录状态及 action。
因此无 reset 时，stock 文件中：

```
state[i] -- action[i+1] --> state[i+1]
q_cmd = q_default + 0.25 * action
```

`delta_a_open_loop.py:138` 的 `episode_length_buf+1` 取 action，与这种 post-step 文件一致。
不能一概把 action 平移；若更换 recorder 为 pre-step 记录，要同时改变 reader 的约定。
`actor_obs` 也是 post-step observation，不应当直接把同行 `(actor_obs, action)` 当成原 policy 的输入输出监督对。
有 terminate 的行可能已经是 reset 后状态，应排除该行并切断前后转移。stock exporter 丢弃前三行，不等于自动切断所有后续 reset。

### 2. 回放 reward 的参考提前一帧

`legged_robot_base.py:239` 在 physics 后将 episode counter 加1；
随后 `motion_tracking.py:236` 又用 `(episode_length_buf+1)*dt` 查询 reference。
例如从文件 state[0] 出发，使用 action[1]，physics 后 counter=1，却拿 state[2] 作 reward reference。
对实际录制数据的动力学校准，这与所执行转移不一致。原 motion policy 的提前参考约定可以保留；补丁只为 DeltaA_OpenLoop 选择当前 post-step 帧。
修正它会改变残差训练目标，应重新训练 delta；旧 checkpoint 只适合另列 legacy 诊断组。

### 3. 闭环残差单位不同

`delta_a_open_loop.py:50,57,92`：实际 PD 目标是 `q_default + scale*(a+δ)`。
`delta_a_closed_loop.py:65,68,164`：当前实现是 `q_default + scale*a + δ`。
scale=0.25 时，相同网络输出被放大4倍。若上次评估用 open-loop env，此问题不能解释那次结果；若用 closed-loop 接入则直接相关。

### 4. 冻结 delta 看到上一拍 nominal action

`PPODeltaA` 从旧 obs 中先算当前 motion action，又把旧 `closed_loop_actor_obs` 传给 delta。
其中 `actions_sim2real_policy` 在 post-step observation 时构造，所以是上一拍 nominal action。
补丁在加载网络前替换这一 feature，保留状态与上一拍 delta。观测按名字排序，不能按 YAML 列表位置猜 slice。

### 5. 初始化速度不是保存的实际速度

`motion_lib_base.py:401` 调用 FK 重建 reference；`torch_humanoid_batch.py:210–224,272–290` 通过差分/平滑计算速度。
文件保存的 `dof_vel/root_lin_vel/root_ang_vel` 没有被 loader 用作实际初始化速度。
因此即使 Kp 一样，重放也未必近乎零误差。这个补丁没有改速度 loader。
服务器优先检查各速度的坐标系和差异，然后让 reset 使用实际记录速度；不要把关节前向差分与瞬时末速度当成同一量。
接触 solver 隐状态也不能靠 q、qdot 完全恢复；跳跃落地段的回放尤其应单独报告。

### 6. 隐藏的第二个 physics gap

source config `robot.asset.self_collisions=0`，默认 robot YAML 是1。直接复制 README 启动 delta 训练会带来额外的 collision 设置差异。
必须核对 source、collection、delta-training 三份实际 config，不能只看命令中的 ankle 两项。

### 7. 训练窗口和 seed

`sample_time` 默认在完整 trajectory 上均匀采样，环境未传 truncate_time；尾部 start 得不到完整1 s。
如要固定时域实验，应限制起点 `0 <= t0 <= L-H`，最好落在记录帧网格上，并排除 reset。诊断脚本会输出尾部比例。
不能把短1 s窗口直接扔给 stock 随机起点实现，然后假定每次都训练了完整1 s。

`train_agent.py` 中 seeding 调用被注释；对 Gym 仅改 `seed=...` 并不证明 RNG 已初始化。
正式多种子比较要在 Gym 导入后、env/network 实例化前调用 `seeding(config.seed)`，并记录实际训练重复。

## 工具与补丁

`audit_rollout.py` 只做 CPU 文件检查，不证明物理回放正确。
`compare_replay.py` 按 prediction 的 motion_times 对齐 reference 局部时间；输出关节角 RMSE 和 root 位置误差，不是全身 MPJPE。
它要求同一环境 origin、连续 episode；不做最优时间平移、不做逐帧 root 对齐，也不使用 exporter 自带的提前一帧 reference。
预测 dump 的 action 是 delta 自身，不能将它当成原始校准 action 文件继续训练。

补丁涉及 reference hook、closed-loop action scale、当前 action conditioning；原始训练源码未改。
先复制本目录到服务器 ASAP checkout 的同一路径，再检查和应用。补丁改变了残差目标及 fine-tuning 动力学，相关模型需重训。

```bash
# 在服务器 ASAP repo 根目录；先激活其已有 hvgym 环境
git apply --check research/asap_diagnostics/timing_and_delta_units.patch
python research/asap_diagnostics/verify_contracts.py
git apply research/asap_diagnostics/timing_and_delta_units.patch
```

verify_contracts 在临时目录应用补丁，测试 CPU 张量的尺度、时间与输入约定；没有运行 Gym。
应用补丁之后，该测试会因为补丁已应用而拒绝重复应用，这是预期行为。

## 服务器执行顺序

### A. 先用 SquatL1 采集一条短目标轨迹

下面的相对路径按当前本地目录布局写，服务器应替换成自己的真实路径。
190步约3.8 s，短于 SquatL1 参考；若过程中发生 reset，要切分后使用，不能依靠固定步数避免失败 reset。

```bash
python humanoidverse/eval_agent.py \
  +checkpoint=logs/SquatL1/model_6000.pt \
  +headless=True +num_envs=1 +opt=record \
  ++env.config.save_motion=True \
  ++env.config.save_total_steps=190 \
  ++env.config.dump_motion_name=squat_anklekp080_rollout \
  ++env.config.noise_to_initial_level=0 \
  ++env.config.enforce_randomize_motion_start_eval=False \
  ++robot.control.stiffness.ankle_pitch=16 \
  ++robot.control.stiffness.ankle_roll=16
```

路径会打印，正常在 checkpoint 父目录的 `motions/`；不是自动在全局 `logs/motions/`。
下面 `$CALIB_PKL`、`$DELTA_PT`、`$ZERO_PKL`、`$LEARNED_PKL` 需要赋成实际文件路径。

```bash
python research/asap_diagnostics/audit_rollout.py \
  --source-config logs/SquatL1/config.yaml \
  --rollout "$CALIB_PKL" --horizon 1 \
  --json-out research/asap_diagnostics/rollout_audit.json
```

一条轨迹只用于流程诊断，不支撑数据选择/泛化结论。

### B. 创建 delta 模型，先做少量迭代检查

源仿真保持 Kp20；不要将采集的 Kp16 又复制进源仿真。
不加载 Squat policy checkpoint 来初始化 delta，它的观测网络不同。
以下100轮用于获得可加载模型和检查日志，不能作为收敛保证。
为了隔离问题，先关闭 delta 的两项额外观测噪声，并只允许 ankle 物理修正。mask 仍是23维网络。

```bash
python humanoidverse/train_agent.py \
  +simulator=isaacgym +exp=train_delta_a_open_loop \
  +domain_rand=NO_domain_rand \
  +rewards=motion_tracking/delta_a/reward_delta_a_openloop \
  +robot=g1/g1_29dof_anneal_23dof \
  +terrain=terrain_locomotion_plane +obs=delta_a/open_loop \
  num_envs=2048 headless=True \
  project_name=DeltaA_Diagnostic experiment_name=Squat_Kp080 \
  robot.motion.motion_file="$CALIB_PKL" \
  robot.control.stiffness.ankle_pitch=20 \
  robot.control.stiffness.ankle_roll=20 \
  robot.asset.self_collisions=0 \
  env.config.max_episode_length_s=1.0 \
  env.config.noise_to_initial_level=0 \
  env.config.resample_motion_when_training=True \
  env.config.resample_time_interval_s=10000 \
  ++env.config.anklePR=True \
  obs.noise_scales.base_pos_z=0.0 \
  obs.noise_scales.feet_contact_force=0.0 \
  rewards.reward_scales.penalty_minimal_action_norm=-0.1 \
  algo.config.init_at_random_ep_len=False \
  algo.config.num_learning_iterations=100 algo.config.save_interval=50
```

这些命令没有经过本次 GPU 运行验证。正式固定时域实验还需要上面的有效起点限制和实际速度初始化。
不要把固定迭代数当成已收敛；通过独立回放曲线决定是否值得延长到1000轮。

### C. 三项回放比较

所有评估载入 delta checkpoint 的 config/obs，reference 仍是 `$CALIB_PKL`。
**不载入 Squat policy 来重算 nominal action。** nominal action 由 motion file 读取。

第一项：B→B、δ=0，用来量化 recorder/loader/reset 的误差底线。

```bash
python humanoidverse/eval_agent.py \
  +checkpoint="$DELTA_PT" +headless=True +num_envs=1 +opt=record \
  ++robot.motion.motion_file="$CALIB_PKL" \
  ++robot.control.stiffness.ankle_pitch=16 \
  ++robot.control.stiffness.ankle_roll=16 \
  ++robot.asset.self_collisions=0 \
  ++env.config.add_extra_action=True \
  ++env.config.zero_delta_a=True ++env.config.anklePR=True \
  ++env.config.enforce_randomize_motion_start_eval=False \
  ++env.config.save_motion=True ++env.config.save_total_steps=55 \
  ++env.config.dump_motion_name=replay_same_domain_zero
```

如果这项误差明显，先处理实际速度、接触初始化、索引和坐标；暂停增加 delta 训练时间。

第二项：B data→A、δ=0：上面两个Kp改为20，dump名字改为 `replay_source_zero`。
第三项：B data→A、learned δ：Kp保持20，`zero_delta_a=False`，名字改为 `replay_source_learned`。
其他配置、reference和reset保持一致。stock eval 会导出 ONNX，这与回放是否成功无关。

```bash
python research/asap_diagnostics/compare_replay.py \
  --reference "$CALIB_PKL" --prediction "$ZERO_PKL" --horizon 1 \
  --json-out research/asap_diagnostics/source_zero_metrics.json
python research/asap_diagnostics/compare_replay.py \
  --reference "$CALIB_PKL" --prediction "$LEARNED_PKL" --horizon 1 \
  --json-out research/asap_diagnostics/source_learned_metrics.json
```

另外分别测 horizon0.25、0.5；同域回放也用同一工具比较。
输出会报告首个被比较时间，不能称为从t=0完整覆盖；stock recorder有前三行裁剪。
如有 reset，工具仅统计首次 reset 前，务必同时报告提前终止，不能用较短序列均值与完整序列混比。
即使 learned 在唯一训练轨迹上优于 zero，也只证明拟合流程可用。

### D. 解析残差作为解释性对照

只改变 Kp：β=16/20=0.8，Kd相同。在同一瞬时状态：

```
e = q_default + action_scale * a - q
delta_q = (beta - 1) * e
delta_action = delta_q / action_scale
```

所以本例 ankle `delta_action=-0.8*e`，不是 `+0.8*e`。
若在 `_compute_torques` 中直接替换 `actions_scaled`，应使用 `-0.2*e`（rad），不要再乘scale。
仅4个 ankle indices [4,5,10,11] 非零。
源码的 `_get_perfect_delta_a` 写死0.65 Kp案例（-0.35），不能当成本实验0.8 Kp oracle。
每个200 Hz PD子步重算可匹配瞬时力矩；50 Hz更新并保持的解析残差不能宣称整段严格等价。
因此高频oracle仅作接口诊断，正式比较应另列同50 Hz解析基线。

### E. 再进入闭环微调

通过独立回放验证后，冻结新的 delta，从同一 Squat/Step source `.pt` 出发，在 A+δ 微调。
`robot.motion.motion_file` 换回 source config 里的原始 reference；不要继续用目标域失真 rollout。
源 gains20、self_collisions0、mask相同，delta输入噪声配置与训练一致。
eval目标域B时物理注入delta要关掉：stock closed-loop env 可以用 `env.config.add_extra_action=False`。
此方式仍会加载/推理冻结delta，但不会加到PD目标。与真正删除delta网络部署区分开。
比较原π0、FT-only、A+δ微调后的policy；后两组相同起点与PPO预算。

## 研究问题与假设：不把特征限定死在 actuator ROM

问题：固定校准预算时，哪些连续状态动作片段改善ASAP的目标域闭环控制？为何未见轨迹回放误差降低不一定转化成控制收益？

假设：有效数据同时需要（i）揭示动力学差异，（ii）覆盖后续policy会访问且对稳定/任务有影响的状态动作区域。
单纯ROM宽、大累计漂移、运动名字多，分别都不是充分条件。
简单Kp条件中，位置指令误差e比绝对角度ROM更直接；其他mismatch可能需要速度、频率、历史、接触负载等。
Kp差异有已知解析解，因此更适合作为pipeline诊断与解释性控制条件；单凭这个条件不足以展示通用数据选择方法的价值。
如有时间，第二种gap可选Kd变化或非线性力矩衰减，先检查目标域任务确实受到影响且仍可改善。
对Kd变化，同状态未截断PD力矩的匹配修正为 `delta_q = -(Kd_B-Kd_A)*qdot/Kp_A`，说明信息特征应随gap改变。

最小等预算组：Random-N、ROM/Excitation-N、HighShortHorizonError-N、Coverage-N，另加Random-2N判断数量收益。
时间不足先做Random-N、Coverage-N、Random-2N。
误差selector必须从相同初始化的短回放计算；不能用整条rollout的末端漂移排序。
按完整rollout先分train/validation/test，再切窗口；相邻窗口不能跨集合。
确定分箱/selector只看calibration训练池。固定unique转移数、窗口时域、网络、mask、reward、PPO环境步数和fine-tuning起点。
从已采完的池里选子集只能说明数据利用效率，不能说明采集成本下降。
多个没有扰动的确定性repeat也可能只提供重复转移，不能把rollout次数直接当作数据多样性。

研究Fig10瓶颈的四个可区分机制：

| 假设 | 诊断干预 | 哪种结果更支持它 |
|---|---|---|
| 更多数据主要改善控制不敏感区域 | 分接触阶段/关节统计；源域小扰动估计有限时域任务/稳定性敏感性，单独评策略占据区域 | 总开环更低，但关键区域误差/闭环都不改善 |
| 微调造成分布漂移 | 记录πFT在B的状态动作，并算其训练覆盖外比例；小预算补采这些区域 | 补采关键区域比等量旧分布数据更能改善闭环 |
| policy优化/可达性瓶颈 | 在已知B中从同一π0直接微调，使用相同任务reward/训练预算 | B直接微调也停在类似位置，数据改善很难转成更好控制 |
| 残差存在拟合偏差/被policy利用 | 在πFT自身B轨迹上重放，比较A+δ与B，并统计修正幅度/接触异常 | 旧policy的OOD回放好，但πFT轨迹上的回放仍差 |

目标域直接微调是参考对照，不是严格数学上界；若其表现差，要区分等预算训练不足与动力学限制。
至少对关键比较做2–3个独立训练重复。没有误差条的细小变化不能证明加数据有害。

Fig10读数在用户memo中为：OOD49.43→41.33→39.44→28.10 mm；closed534.02→104.95→97.51→98.15 mm。
正文将最后一段描述为下降约0.65%，与图中最后两数方向不一致。用“后两组近似饱和”表述，不推断统计显著变差，也不拟合所谓scaling law。
图的数据规模单位不能擅自解释成记录帧数；自己的预算要明示有效秒数/unique转移数/完整rollout数。

优先交付可解释的负结果与受控干预；若只完成开环，不把闭环假设写成已验证结论。

## 阅读来源

- [ASAP v3](https://arxiv.org/html/2502.01143v3)：III阶段与V-A消融。
- [SPI-Active](https://arxiv.org/html/2505.14266v1)：信息驱动的激励与下游控制。
- [UAN](https://arxiv.org/html/2502.10894v1)：不同激励序列覆盖与未见投掷测试。
- Private research brief and lab recruitment context (not distributed in this repository).

这些已有研究约束新颖性：不能宣称首次提出“有信息的数据比随机数据好”。本问题的可评估价值是ASAP中数据内容、回放指标、闭环收益之间的受控诊断。
