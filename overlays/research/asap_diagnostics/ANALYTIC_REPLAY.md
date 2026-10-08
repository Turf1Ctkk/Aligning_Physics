# 已见 Squat 数据拟合后的解析对照

本次服务器结果：zero 的1 s ankle RMSE 0.035351 rad、root平均误差22.383 mm；
learned500为0.049922 rad、6.857 mm，learned1000为0.058322 rad、7.239 mm。
500轮root降低约69.4%，ankle升高约41.2%。root是累计平均位置误差，不是终点误差或全身MPJPE。
这些结果支持“部分回放指标改善”，尚不能判断整体校准、泛化或闭环收益。

当前奖励包含全身位置、脚位置、全身旋转/速度和23关节的平均角度/速度误差，
还包含残差范数、动作变化、关节限位、速度限位及力矩约束。奖励取舍是候选解释，尚未验证。
训练随机起点包括非采样网格和不足完整1 s的尾段，也可能使训练与起点0的评估不同。
该解析实验不使用训练奖励或随机起点，所以可以先区分控制接口/频率限制与学习目标问题。

对同一瞬时状态，Kp_source=20、Kp_target=16、Kd相同、action_scale=s时：

```
tau_target = 16 * (s*a + q_default - q) - Kd*qdot
tau_source = 20 * (s*(a+delta) + q_default - q) - Kd*qdot
delta = (16/20 - 1) * (a + (q_default-q)/s)
```

只有四个ankle输出非零。该解析残差知道目标增益，是诊断对照，不是未知现实动力学的校准方法。

- `analytic50`：每个控制步计算一次，然后与policy一样保持四个物理子步；动作限幅与policy一致。
- `analytic200`：每个物理子步用当前关节角度重新计算；检查瞬时力矩等价能否恢复回放。
  它具有比policy更高的更新频率，不能当作同频学习模型的性能界限。
- 如果解析残差超出policy action bound，脚本报错，避免忽略饱和而宣称完全等价。
- 200 Hz回放的导出action只表示该控制步第一个残差值，不能用于新的delta训练数据。

## 服务器操作

将`analytic_replay_update.zip`上传至ASAP根目录，在已激活的hvgym环境执行：

```bash
cd ~/ASAP
unzip -o analytic_replay_update.zip
bash research/asap_diagnostics/run_analytic_replay.sh
```

无需新核心补丁；诊断子类仅通过本次eval的Hydra env._target_显式选择。
脚本默认使用fit_recorded_20261008_021017的model_500.pt和既有Kp16采集文件。
可通过ASAP_DIAG_FIT_ID、ASAP_DIAG_RUN_ID、ASAP_DIAG_CALIB_PKL覆盖路径。
重测zero/learned500及50/200 Hz解析残差，生成12个JSON。
原训练文件和既有回放保持不变，新预测PKL位于原FIT_DIR/motions的新时间戳文件下。

## 如何解释

1. zero/learned500复测应接近旧结果；明显改变时先核对评估配置。
2. analytic200接近同域误差量级时，已知Kp差异通过残差消除的物理接口得到支持。
   如果仍明显偏离，先检查实际力矩/增益/子步状态更新，不能据此增加数据或训练次数。
3. analytic50也同时降低关节和root误差时，50 Hz下存在一个有效补偿基线；
   learned的取舍更值得从奖励、优化和起点采样检查。它不证明是哪一项导致。
4. analytic200好、analytic50差时，更新频率/保持方式可能有贡献。
   analytic50是瞬时补偿公式的保持实现，不是50 Hz可实现误差的最优下界。
5. 学习模型的论文级评估仍需全身MPJPE、足端误差、不同初始片段和独立rollout；
   这次只比较同一轨迹前1 s，尚未进行后续policy训练或闭环测试。

本地验证：CPU公式、ankle mask、50 Hz保持/200 Hz重算派发、动作饱和检查、shell语法。
本地没有执行IsaacGym物理回放或训练，物理结论需服务器输出。
