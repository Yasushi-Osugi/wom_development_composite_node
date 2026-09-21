"""
wom_rl_framework.py
===================
サプライチェーン計画のための強化学習フレームワーク（試作版）
WOM (Weekly Operation Model) v1r0m3 に対応した Q-learning エージェント

概念マッピング:
  SCState      ← WOM の psi4supply[w] スナップショット（簡略版）
  Operator     ← WOM Planning Engine Operator
  U(S)         ← WOM 評価関数（サービス率・利益・在庫コスト）
  WOMEnv       ← WOM Flow Engine（シミュレーター）
  WOMRLAgent   ← Resolver（将来のRL実装の原型）

依存ライブラリ: Python標準ライブラリのみ（numpy不要）
実行方法: python wom_rl_framework.py
"""

import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ─────────────────────────────────────────────────────────────────
# 1. SCState  ── サプライチェーン状態（WOM PSI の簡略表現）
# ─────────────────────────────────────────────────────────────────

@dataclass
class SCState:
    """
    Week t における SC の snapshot。
    WOM の psi4supply[w][S,CO,I,P] を連続値で近似したもの。
    """
    week:      int
    inventory: float   # Buffer 在庫（lots） ← MOM.psi4supply[w][I]
    demand:    float   # 今週の需要（lots）  ← leaf_out.demand[w]
    capacity:  float   # 工場週次能力（lots）← AssemblyCN.cap_hard
    backlog:   float = 0.0  # 繰越未充足需要（CO）

    def to_key(self) -> tuple:
        """Q-table のキー（状態を離散化）"""
        return (
            min(int(self.inventory / 100), 30),  # 在庫レベル 0-30
            min(int(self.demand    / 100), 20),  # 需要レベル 0-20
            min(int(self.backlog   /  50), 10),  # 繰越レベル 0-10
        )


# ─────────────────────────────────────────────────────────────────
# 2. Planning Operators  ── 意思決定の選択肢
# ─────────────────────────────────────────────────────────────────

class Operator:
    """WOM Planning Operator の基底クラス"""
    name: str = "BaseOperator"

    def apply(self, s: SCState) -> SCState:
        raise NotImplementedError


class NormalProdOperator(Operator):
    """通常生産: 需要 + 繰越分だけ生産（標準Operator）"""
    name = "NormalProd"

    def apply(self, s: SCState) -> SCState:
        produce  = min(s.demand + s.backlog, s.capacity)
        delta    = s.inventory + produce - s.demand
        new_inv  = max(delta, 0.0)
        new_back = max(-delta, 0.0) + max(s.backlog - produce, 0.0)
        return SCState(s.week + 1, new_inv, s.demand, s.capacity, new_back)


class PrebuildOperator(Operator):
    """先行生産（PUSH Mode 4）: 能力フル稼働でバッファ積み上げ"""
    name = "Prebuild"

    def apply(self, s: SCState) -> SCState:
        produce  = s.capacity  # フル稼働
        delta    = s.inventory + produce - s.demand
        new_inv  = max(delta, 0.0)
        new_back = max(-delta, 0.0)
        return SCState(s.week + 1, new_inv, s.demand, s.capacity, new_back)


class ConserveOperator(Operator):
    """節約生産: 需要の 50% のみ生産（コスト削減フェーズ）"""
    name = "Conserve"

    def apply(self, s: SCState) -> SCState:
        produce  = min(s.demand * 0.5, s.capacity)
        delta    = s.inventory + produce - s.demand
        new_inv  = max(delta, 0.0)
        new_back = max(-delta, 0.0)
        return SCState(s.week + 1, new_inv, s.demand, s.capacity, new_back)


class EmergencyReplenishOperator(Operator):
    """緊急補充: 在庫逼迫時に残業で能力×1.2 生産"""
    name = "Emergency"

    def apply(self, s: SCState) -> SCState:
        produce  = min(s.demand + s.backlog, s.capacity * 1.2)
        delta    = s.inventory + produce - s.demand
        new_inv  = max(delta, 0.0)
        new_back = max(-delta, 0.0) + max(s.backlog - produce, 0.0)
        return SCState(s.week + 1, new_inv, s.demand, s.capacity, new_back)


class StaircaseDownOperator(Operator):
    """段階縮小生産（DBR Staircase）: 製品 EOL フェーズで能力を 2/3 に絞る"""
    name = "StaircaseDown"

    def apply(self, s: SCState) -> SCState:
        produce  = min(s.demand + s.backlog, s.capacity * 0.67)
        delta    = s.inventory + produce - s.demand
        new_inv  = max(delta, 0.0)
        new_back = max(-delta, 0.0) + max(s.backlog - produce, 0.0)
        return SCState(s.week + 1, new_inv, s.demand, s.capacity, new_back)


# ─────────────────────────────────────────────────────────────────
# 3. Evaluation Function U(S)  ── WOM 評価関数（報酬）
# ─────────────────────────────────────────────────────────────────

def evaluate(state: SCState) -> float:
    """
    U(S) = w1 × service_rate  （サービス充足率: 売上・顧客満足）
         - w2 × inventory_cost （在庫保管コスト: 資本効率）
         - w3 × backlog_penalty（欠品ペナルティ: 機会損失）

    重み w は「何を優先するか」というビジネス哲学を反映する。
    """
    service_rate     = 1.0 - min(state.backlog / max(state.demand, 1.0), 1.0)
    inventory_cost   = state.inventory * 0.008   # 在庫 1 lot あたりの週次保管コスト
    backlog_penalty  = state.backlog   * 0.6     # 欠品 1 lot あたりのペナルティ（重く設定）

    return (
        + 1.5 * service_rate
        - 0.3 * inventory_cost
        - 2.0 * backlog_penalty
    )


# ─────────────────────────────────────────────────────────────────
# 4. WOMRLAgent  ── Q-learning エージェント（Resolver の原型）
# ─────────────────────────────────────────────────────────────────

class WOMRLAgent:
    """
    Q-learning を用いた WOM Planning Operator 選択エージェント。

    学習対象: 状態 S のとき、どの Operator を選べば
             累積 U(S) が最大になるか？

    アルゴリズム: ε-greedy + Bellman 更新
        Q(s,a) ← Q(s,a) + lr × [r + γ × max_a' Q(s',a') - Q(s,a)]
    """

    def __init__(
        self,
        operators: List[Operator],
        lr:      float = 0.1,   # 学習率（Learning Rate）
        gamma:   float = 0.95,  # 将来報酬の割引率（Discount Factor）
        epsilon: float = 0.4,   # 探索率（ε-greedy）
    ):
        self.operators = operators
        self.lr        = lr
        self.gamma     = gamma
        self.epsilon   = epsilon
        # Q-table: state_key → [Q値 per operator]
        self.q_table: Dict[tuple, List[float]] = {}

    def _get_q(self, key: tuple) -> List[float]:
        if key not in self.q_table:
            self.q_table[key] = [0.0] * len(self.operators)
        return self.q_table[key]

    def choose_action(self, state: SCState) -> Tuple[int, Operator]:
        """ε-greedy: 確率 ε でランダム探索、1-ε で最良 Operator 選択"""
        if random.random() < self.epsilon:
            idx = random.randrange(len(self.operators))
        else:
            key    = state.to_key()
            q_vals = self._get_q(key)
            idx    = q_vals.index(max(q_vals))
        return idx, self.operators[idx]

    def learn(
        self,
        state:      SCState,
        action_idx: int,
        reward:     float,
        next_state: SCState,
    ) -> None:
        """Bellman 方程式で Q 値を更新する"""
        s_key  = state.to_key()
        ns_key = next_state.to_key()

        current_q  = self._get_q(s_key)[action_idx]
        max_next_q = max(self._get_q(ns_key))

        # Q(s,a) ← Q(s,a) + lr × [r + γ × max Q(s') - Q(s,a)]
        new_q = current_q + self.lr * (
            reward + self.gamma * max_next_q - current_q
        )
        self._get_q(s_key)[action_idx] = new_q

    def best_operator(self, state: SCState) -> str:
        """現在の最良 Operator 名を返す（可視化用）"""
        key    = state.to_key()
        q_vals = self._get_q(key)
        idx    = q_vals.index(max(q_vals))
        return self.operators[idx].name


# ─────────────────────────────────────────────────────────────────
# 5. WOMEnvironment  ── Flow Engine（シミュレーター）
# ─────────────────────────────────────────────────────────────────

class WOMEnvironment:
    """
    WOM Flow Engine の簡易実装。
    SmartXPro の製品ライフサイクル需要カーブをシミュレートする。

    需要パターン（CLAUDE.md の DBR 設計に対応）:
      W01-W10 : ランプアップ（200→800 lots/wk）
      W11-W35 : ピーク期   （800 lots/wk ± ノイズ）
      W36-W45 : 下降期     （次世代モデル登場）
      W46-W52 : EOL 期     （在庫消化フェーズ）
    """

    def __init__(self, n_weeks: int = 52, seed: int = 42):
        self.n_weeks = n_weeks
        random.seed(seed)
        self.demands = self._generate_lifecycle_demand(n_weeks)

    def _generate_lifecycle_demand(self, n: int) -> List[float]:
        """SmartXPro ライフサイクル需要生成"""
        demands = []
        for w in range(n):
            if w < 10:
                d = 200.0 + w * 60.0
            elif w < 35:
                d = 800.0 + random.gauss(0, 40)
            elif w < 45:
                d = max(200.0, 800.0 - (w - 35) * 50.0 + random.gauss(0, 25))
            else:
                d = max(50.0, 200.0 - (w - 45) * 25.0)
            demands.append(max(0.0, d))
        return demands

    def reset(self) -> SCState:
        """エピソード開始: 初期状態を返す"""
        self.week = 0
        return SCState(
            week      = 0,
            inventory = 400.0,   # 初期在庫（Buffer_Chip_TW の期初在庫）
            demand    = self.demands[0],
            capacity  = 900.0,   # AssemblyCN cap_hard（ピーク期）
        )

    def step(
        self, state: SCState, operator: Operator
    ) -> Tuple[SCState, float, bool]:
        """
        1 週間進める。
        Returns: (次の状態, 報酬 U(S), 終了フラグ)
        """
        next_state        = operator.apply(state)
        self.week        += 1
        done              = self.week >= self.n_weeks
        if not done:
            next_state.demand = self.demands[self.week]
        reward            = evaluate(next_state)
        return next_state, reward, done


# ─────────────────────────────────────────────────────────────────
# 6. Training Loop  ── 学習ループ
# ─────────────────────────────────────────────────────────────────

def train(
    episodes: int = 500,
    n_weeks:  int = 52,
    verbose:  bool = True,
) -> Tuple["WOMRLAgent", List[float]]:
    """
    Q-learning エージェントを訓練する。

    Returns:
        agent          : 学習済みエージェント
        episode_rewards: 各エピソードの累積報酬リスト
    """
    operators = [
        NormalProdOperator(),
        PrebuildOperator(),
        ConserveOperator(),
        EmergencyReplenishOperator(),
        StaircaseDownOperator(),
    ]
    env   = WOMEnvironment(n_weeks)
    agent = WOMRLAgent(operators, epsilon=0.4)

    episode_rewards: List[float] = []

    for ep in range(episodes):
        state        = env.reset()
        total_reward = 0.0

        while True:
            action_idx, operator         = agent.choose_action(state)
            next_state, reward, done     = env.step(state, operator)
            agent.learn(state, action_idx, reward, next_state)
            total_reward                += reward
            state                        = next_state
            if done:
                break

        # 探索率を徐々に下げる（exploitation の割合を増やす）
        agent.epsilon = max(0.05, agent.epsilon * 0.995)
        episode_rewards.append(total_reward)

        if verbose and (ep + 1) % 100 == 0:
            avg = sum(episode_rewards[-100:]) / 100
            print(
                f"Episode {ep+1:4d} | "
                f"Avg Reward (直近100ep): {avg:7.3f} | "
                f"ε: {agent.epsilon:.3f} | "
                f"Q-states: {len(agent.q_table):4d}"
            )

    return agent, episode_rewards


# ─────────────────────────────────────────────────────────────────
# 7. Evaluation  ── 学習済みエージェントの動作確認
# ─────────────────────────────────────────────────────────────────

def run_episode(agent: "WOMRLAgent", n_weeks: int = 52) -> None:
    """学習済みエージェントでの 1 シーズン計画を表示する"""
    env           = WOMEnvironment(n_weeks, seed=99)  # 訓練と別シード
    agent.epsilon = 0.0   # 探索なし → 最良 Operator のみ選択
    state         = env.reset()

    print("\n" + "=" * 70)
    print("  学習済みエージェントの SC 計画（52週）")
    print("=" * 70)
    print(
        f"{'Wk':>3} {'Demand':>7} {'Inv':>7} {'Backlog':>8} "
        f"{'Operator':<20} {'U(S)':>7}"
    )
    print("-" * 70)

    total_reward   = 0.0
    total_backlog  = 0.0
    total_service  = 0.0

    while True:
        action_idx, operator         = agent.choose_action(state)
        next_state, reward, done     = env.step(state, operator)
        total_reward                += reward
        total_backlog               += next_state.backlog
        svc = 1.0 - min(next_state.backlog / max(next_state.demand, 1.0), 1.0)
        total_service               += svc

        print(
            f"{state.week:>3} {state.demand:>7.0f} {state.inventory:>7.0f} "
            f"{state.backlog:>8.0f} {operator.name:<20} {reward:>7.3f}"
        )
        state = next_state
        if done:
            break

    print("-" * 70)
    print(f"  累積 U(S)     : {total_reward:>8.3f}")
    print(f"  平均サービス率: {total_service / n_weeks * 100:>7.1f}%")
    print(f"  累積繰越需要  : {total_backlog:>8.0f} lots")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("  WOM 強化学習フレームワーク（試作版）")
    print("  S* = argmax U(T(S0, A))  ──  Q-learning 実装")
    print("=" * 70)
    print()
    print("[学習フェーズ] 500 エピソード × 52 週")
    print()

    agent, rewards = train(episodes=500, n_weeks=52)

    print()
    print("[評価フェーズ] 学習済みエージェントによる 52 週計画")
    run_episode(agent, n_weeks=52)

    # 学習曲線のサマリー
    n = len(rewards)
    early_avg = sum(rewards[:100])  / 100
    late_avg  = sum(rewards[-100:]) / 100
    print()
    print(f"[学習曲線] 初期100ep 平均報酬: {early_avg:.3f}  →  "
          f"最終100ep 平均報酬: {late_avg:.3f}  "
          f"（改善率: {(late_avg - early_avg) / abs(early_avg) * 100:.1f}%）")
