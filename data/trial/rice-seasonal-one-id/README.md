# Rice 1品目・1需要IDの検算用入力

通常Riceの置換モデルではありません。起動は tools.probe_rice_seasonal_definition を使います。

- 経路・LT: 基準26a1e8eのRice Koshihikari/KANSAI経路の7ノードを抽出。
- 精米10 kg/需要lot、歩留まり0.9、収穫・保管能力、期間の上限は検算用の仮の値。
- 需要CSVはPlanning経路の需要lot数（1）。現行headlessと同じくID生成はcpu_size=1で行い、設定cpu_size=10は1需要lotの精米kg換算に使います。需要をもう一度10で割りません。
- capacity_plan.csvの値は最終需要lot相当。kg能力はscenario.jsonから独立した資源問題に明示換算します。この換算を通常Riceの既存マスターへ適用したものではありません。
- 非収穫週は0で明示。0.1による整数化に依存しません。前倒し計画を試作から内部ノードに渡し、同じIDの玄米保管・精米・販売を既存Forwardで観測します。
- 仮想SPのPSIは既存木との接続を確認する記録であり、物理輸送・物理保管のノードではありません。
- 価格・原価・PPC/Value Chainマスターはありません。kg台帳は物量の検算で、金額評価を行いません。
- scenario.jsonのexpectedは手計算値です。結果に合わせて書き換えません。
