# 三类动作、多 rollout 的 delta 数据规模实验

论文依据：ASAP III-A/III-B 与 Fig.5明确采用多policy/motion的目标域rollout；
IV-C报告5类真实任务、100条motion clips、4-DoF ankle delta。
同段另写每任务执行tracking policy 30次，没有解释与100条训练clips的对应关系。
“超过400条”是论文23-DoF设置的实验观察，不能直接套用到这里的4-DoF、纯Kp差异实验。
来源：https://arxiv.org/html/2502.01143v3

解析补偿只验证实现/可补偿性，不作为学习模型的成绩、训练标签或本次数据筛选依据。
本轮从Kp16域采集CR7、SquatL1、StepFBL1预训练policy的rollout，在Kp20域学习delta。
这仍然是同一个IsaacGym的参数域迁移，不是论文IsaacSim/Gym或真实G1实验的等价复现。

## 默认实验

| 项目 | 设置 |
|---|---|
| 目标域 | ankle pitch/roll Kp16；其他动力学保持一致 |
| 源域 | Kp20；Kd pitch0.2、roll0.1；action_scale0.25 |
| 数据 | 三类动作各40个并行环境rollout，总计120个原始rollout |
| 多样性 | 每个环境独立随机初始状态扰动；三个不同motion与policy |
| 扰动 | noise_to_initial_level0.2：默认关节位置std约0.02rad、速度std约0.03rad/s；root位置/姿态扰动设0；root线/角速度使用原init_noise_scale乘0.2 |
| 固定条件 | 不随机Kp、质量、摩擦、控制延迟或外力；不注入解析delta |
| 划分 | 每类env0–29训练、30–34验证、35–39测试；在切片之前按整个环境rollout划分 |
| 数据规模 | balanced1每类1个训练rollout；balanced10每类10个；balanced_full每类最多30个 |
| 训练 | 每组从头训练1000 PPO iterations；2048环境；1s时域；4踝关节mask；同奖励及随机种子 |
| 起点 | 记录帧网格上随机抽样，预留完整episode时长；兼容原timeout的多一个控制步 |
| checkpoint | 验证集选500或1000轮；所选模型再测测试集 |
| 测试范围 | 同三类motion的未见rollout；每个片段取开头、中部、末尾的1s窗口 |

如果轨迹有reset，重置行被移除，前后分成独立连续片段，但属于同一环境rollout的片段保持在同一数据分区。
不足完整1s的片段单独记录淘汰原因，原始文件仍保留；不按“动作成功/误差小”筛数据。
精确重复片段按joint state/velocity/action哈希排除；这不检测所有近似重复。
dataset_audit.json报告实际可用数量、reset/短片段和首帧ankle离散程度。
balanced_full使用三类动作中可用训练rollout数量的最小值，保证均衡；实际数量可能少于90。
每个任务至少需要10个有效、非精确重复的训练rollout，否则停止并保留审计报告。

规模组按固定顺序嵌套；改变数据数量，保持motion类别、奖励、模型、训练步数和评估集一致。
本轮也改用了完整网格起点与新的批量记录/评价方式，所以不把旧的单条Squat模型与新模型之差完全归因于数据数量；
本轮三个规模组之间的对比才是当前较受控的数据规模比较。
记录rollout数、连续clip数、transition数和合法1s起点数，避免把它们统称为samples。
这是一轮固定训练预算/单种子的初步数据规模实验，不是统计显著性结论。
三类动作都进入训练，所以held-out测试是未见轨迹的ID测试，不是跨motion OOD。
后续跨motion泛化可另设只训练Squat+Step、完整留出CR7的实验。

## 在服务器挂后台任务

上传multi_motion_update.zip到ASAP根目录，在激活hvgym后执行：

```bash
cd ~/ASAP
unzip -o multi_motion_update.zip
python research/asap_diagnostics/verify_multi_motion.py

RUN_DIR="$PWD/logs/DeltaA_MultiMotion/multi_$(date +%Y%m%d_%H%M%S)"
python research/asap_diagnostics/multi_motion_pipeline.py prepare --work-dir "$RUN_DIR"

nohup python -u research/asap_diagnostics/multi_motion_pipeline.py run \
  --work-dir "$RUN_DIR" > "$RUN_DIR/pipeline.log" 2>&1 < /dev/null &
PIPELINE_PID=$!
echo "PID=$PIPELINE_PID"
echo "RUN_DIR=$RUN_DIR"
tail -f "$RUN_DIR/pipeline.log"
```

自动识别logs下三类预训练policy：按source config中的motion/experiment name匹配，选择最新修改的checkpoint。
prepare输出三条checkpoint路径，并冻结plan.json；未找到时明确报错，不自动训练新的motion policy。
如果需指定版本，把prepare一行替换为：

```bash
python research/asap_diagnostics/multi_motion_pipeline.py prepare \
  --work-dir "$RUN_DIR" \
  --cr7 /absolute/path/model_8000.pt \
  --squat /absolute/path/model_6000.pt \
  --step /absolute/path/model_6000.pt
```

不要把示例占位路径直接执行。CPU verifier只测试逻辑，不启动Gym或训练。
verify_multi_motion.py使用自带临时fixture，不读取logs/SquatL1或任何用户训练目录。
三个checkpoint全部显式指定时，prepare完全跳过logs自动搜索；各.pt同目录或其上一级需有config.yaml。
路径会写入新RUN_DIR的plan.json；已有plan不会被prepare覆盖，修改checkpoint应使用新的RUN_DIR。
GPU任务串行运行，避免三个训练进程争用同一张4090。
tail的Ctrl+C仅停止看日志，nohup进程继续。
查看当前训练详情：例如tail -f "$RUN_DIR/models/balanced_full.log"。

也可以分阶段执行同一脚本的collect、build、train、evaluate子命令。
已有完整raw文件和最终checkpoint会跳过；未完成的训练目录不会自动接着旧checkpoint训，
因为原PPO中间checkpoint的iter字段不足以可靠恢复。保留/重命名未完成目录后再运行train。
收集/评估异常时完整命令保存在对应.command.json，末尾日志会写入pipeline.log。

## 记录器和评价的变化

新增RolloutRecorderPPO显式记录最后一次初始化后的第一步和随后的policy评估步，
不记录构建算法时的setup reset，也不使用stock recorder丢前三帧的规则。
状态与action仍是post-step记录：state[i] -- action[i+1] --> state[i+1]。
每个环境的root与24个实际刚体位置减去env_origins，速度保留世界坐标。
body_pos是物理仿真tensor的实际位置，不是FK重新算出来的位置。
GridDeltaReplay在eval时重新按字典顺序加载全部case，确保预测环境与reference key一一对应。
所有新类仅在本实验Hydra target中选择，不修改正常训练入口和核心repo文件。
seeded_entry先import IsaacGym再import torch，实际初始化Python/NumPy/Torch RNG；不声称GPU物理逐位确定。

validation/test均运行Kp16+zero同域对照、Kp20+zero未校准基线；学习模型保持Kp20。
输出0.25/0.5/1s前缀的ankle角度、23关节角度、关节速度、root位置、
24-body global MPJPE、root-relative MPJPE、双足位置误差和完整帧覆盖率。
MPJPE是与Kp16 rollout的回放误差，尚未fine-tune原motion policy，因此不属于闭环tracking成绩。
24-body的定义应单独写清，不直接等同论文可能采用的body/extended-marker集合。
多个窗口属于同一rollout，先在rollout内平均，再在task内平均，最后三类task等权平均，
避免把相关窗口当作独立样本或让长轨迹/多片段动作占主导。

## 主要输出

- plan.json：三份checkpoint、种子、训练设置。
- collection_configs/*/config.yaml：各采集环境最终配置。
- raw/*.pkl：120条原始rollout，含reset行，完整保留。
- dataset_audit.json、dataset_summary.json：划分、排除原因、实际数据数量。
- datasets/balanced*.pkl、val/test.pkl、val/test_cases.pkl：固定训练/验证/测试文件。
- models/balanced*/model_*.pt：三个模型组。
- selected_checkpoints.json：仅按验证集选出的checkpoint。
- evaluation/{val,test}/*：逐case指标、配置、日志和回放。
- comparison.json：每组/每任务/各时域汇总；pipeline.log末尾打印测试集1s表格。

测试集基线也会保存，但只用验证集选择模型。没有调用解析补偿，也没有执行后续policy闭环fine-tuning。

本地验证范围：CPU分段/泄漏检查、嵌套规模、完整网格时域、原点归一化、
24-body指标、eval顺序加载及模拟评估命令流程。未在笔记本执行物理采集/训练，需服务器实际运行。
