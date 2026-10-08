# 2026-10-08 同域回放失配诊断

用户提交的1 s结果：same16_zero ankle0.26186 rad、root393.60 mm；source20_zero ankle0.23758 rad、root381.69 mm；source20_learned ankle0.22076 rad、root376.57 mm。
三组有相同50帧比较时域、没有报告reset。同域误差过大，尚不能将差异主要归因于Kp gap或数据不足。
审计记录188帧、50.0000011176 Hz、无报告reset/时间跳变；差分与记录关节速度的RMSE0.9229 rad/s。

## 确认的接口问题与证据边界

1. `_calc_frame_blend`以float32算 `(time/length)*(T-1)` 后向下取整。记录帧边界附近浮点误差会导致取前一帧。
   状态会插值回接近正确帧，但 `get_motion_actions` 不插值、直接取前一帧action。
   188帧、50 Hz的CPU算例在前55次调用中有21次偏到前一帧，包含首步1→0。
   用用户提供的fps重复检查亦复现该结果。这证明索引有问题，不证明21次错误各自贡献了多少物理误差。
2. 实际记录速度没有用于初始化。增量补丁增加显式opt-in，供stock IsaacGym recorder的世界坐标root速度使用。
   只有关节/root速度被替换；其他body的参考速度仍来自FK，补丁不恢复contact solver隐状态。

原 `timing_and_delta_units.patch` 保留；新 `replay_fidelity.patch`只修改motion_lib_base.py，可独立叠加。
新patch不改变原始retargeted motion的默认速度行为。
近整数frame在1e-4帧容差内吸附，非边界仍使用零阶保持；action没有整体平移。

## 服务器操作

最短入口：上传更新包至ASAP根目录，运行`unzip -o replay_fidelity_update.zip`，
再依次运行`bash research/asap_diagnostics/run_replay_fix.sh inputs`与`bash research/asap_diagnostics/run_replay_fix.sh replay`。
前者应用增量补丁并做CPU输入核查；后者运行下面的三组零残差回放并生成全部比较JSON和1s表格。
脚本默认使用用户本次提交结果中的路径；若路径变化，使用ASAP_DIAG_RUN_ID、ASAP_DIAG_CALIB_PKL覆盖。

把 `replay_fidelity_update.zip` 放到服务器ASAP根目录后，执行：

```bash
cd ~/ASAP
unzip -o replay_fidelity_update.zip

PATCH=research/asap_diagnostics/replay_fidelity.patch
if git apply --reverse --check "$PATCH" 2>/dev/null; then
    echo "回放补丁已应用"
else
    git apply --check "$PATCH" && git apply "$PATCH"
fi

RUN_ID=diag_20261008_012651
RUN_DIR="$PWD/logs/DeltaA_Diagnostic/$RUN_ID"
DELTA_DIR="$RUN_DIR/delta"
DELTA_PT="$DELTA_DIR/model_100.pt"
CALIB_PKL="$PWD/logs/MotionTracking/20261007_101434-MotionTracking_SquatL1-motion_tracking-g1_29dof_anneal_23dof/motions/${RUN_ID}_squat_kp16.pkl"

python research/asap_diagnostics/verify_replay_fidelity.py \
  --rollout "$CALIB_PKL" \
  --collection-config "$RUN_DIR/collect_eval/config.yaml" \
  --replay-config "$RUN_DIR/eval_same16_zero/config.yaml" \
  --json-out "$RUN_DIR/replay_input_check.json"
```

验证工具在临时目录检查，不运行Gym；应用前后都能执行。physics_config_differences_to_review是需人工核对的差异，不是每项都是错误。

定义新的零残差回放函数：

```bash
replay_zero_fixed() {
    local label="$1"
    local kp="$2"
    local recorded_velocity="$3"

    python humanoidverse/eval_agent.py \
      +checkpoint="$DELTA_PT" \
      +headless=True +num_envs=1 +opt=record \
      ++eval_timestamp="$RUN_ID" \
      ++eval_log_dir="$RUN_DIR/eval_$label" \
      ++robot.motion.motion_file="$CALIB_PKL" \
      ++robot.motion.use_recorded_velocities="$recorded_velocity" \
      ++robot.control.stiffness.ankle_pitch="$kp" \
      ++robot.control.stiffness.ankle_roll="$kp" \
      ++robot.asset.self_collisions=0 \
      ++env.config.add_extra_action=True \
      ++env.config.zero_delta_a=True \
      ++env.config.anklePR=True \
      ++env.config.noise_to_initial_level=0 \
      ++env.config.enforce_randomize_motion_start_eval=False \
      ++env.config.save_motion=True \
      ++env.config.save_total_steps=55 \
      ++env.config.dump_motion_name="$label" \
      > "$RUN_DIR/$label.log" 2>&1
}

replay_zero_fixed same16_index 16 False
replay_zero_fixed same16_recorded 16 True
replay_zero_fixed source20_recorded 20 True

for label in same16_index same16_recorded source20_recorded; do
    for horizon in 0.25 0.5 1.0; do
        python research/asap_diagnostics/compare_replay.py \
          --reference "$CALIB_PKL" \
          --prediction "$DELTA_DIR/motions/${RUN_ID}_${label}.pkl" \
          --horizon "$horizon" \
          --json-out "$RUN_DIR/${label}_${horizon}.json"
    done
done
```

所有三个组zero_delta=True，checkpoint仅用于获得compatible env/obs入口，其学习输出不作用于物理。
使用新名称保留旧结果，不重新采集，不再训练delta。

## 判据

- 旧same16_zero→same16_index：检查修正action索引的影响。
- same16_index→same16_recorded：检查用记录速度初始化的影响。
- same16_recorded vs source20_recorded：在更可信回放下检查Kp gap是否可测。
- 若同域仍明显漂移，继续检查physics config、首步状态/输入，以及contact reset，不能宣称patch已使pipeline跑通。
- 提供replay_input_check.json及三组1s JSON继续诊断；不要对一条轨迹的误差设统一成功阈值。
- 同域回放通过后，残差应从头重训，训练时启用robot.motion.use_recorded_velocities=True；旧100轮模型的索引和初始化目标有偏，不能据此续训并解释泛化。

验证范围：补丁应用/源码编译、CPU索引与速度字段回归检查。此次没有服务器物理回放结果。
