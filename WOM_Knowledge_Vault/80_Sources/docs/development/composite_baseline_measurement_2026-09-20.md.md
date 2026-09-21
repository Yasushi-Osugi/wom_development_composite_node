---
tags: [wom, source]
---
# docs/development/composite_baseline_measurement_2026-09-20.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/development/composite_baseline_measurement_2026-09-20.md) · [原文テキスト](../../../90_Raw/docs/development/composite_baseline_measurement_2026-09-20.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Composite Node：初回実測と詳細設計への申し送り
- 結論
- 測定方法と範囲
- 観測結果
- T02：後日揃ってもgateが再処理しない
- T03：既存完成品の引当と重複組立を区別
- T04：部材払出後に完成Pが削られる
- 実モデルの既存確認
- 詳細設計に渡す最小変更案（未実装）
- 再現

## 関連する知識源

- [[80_Sources/tools/probe_composite_baseline.py|tools/probe_composite_baseline.py]]
- [[80_Sources/tests/test_stage3a2_kitting_gate.py|tests/test_stage3a2_kitting_gate.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Composite Node：初回実測と詳細設計への申し送り

基準: `ceef9ee0e357a556fb5959fdb1e49d8b0e670347`

対象: `Yasushi-Osugi/wom_development_composite_node` / `wom-v1r5m0`

実行: 2026-09-20、適合確認済みLinux / Python 3.12.14。
独立worktree: `/workspace/scratch/ae3ea3e36a29/wom_composite_probe`。
既存Linuxコピーの未コミット文書を保持するため、新たなdetached worktreeを使用。

## 結論

通常組立は成立する。遅着kitの再候補化と、能力判定・部材払出・完成計上の
整合には、以下の合成条件で仕様との差分を実測した。
完成品在庫からの出荷引当は成立するが、同じIDの部材も揃っている条件では
追加組立を防げず、完成品数量の保存が崩れる。

この報告は現行測定であり、core改修・golden更新・commit/pushは実施していない。

## 測定方法と範囲

`tools/probe_composite_baseline.py` は既存
`tests/test_stage3a2_kitting_gate.py` の `_build_tree` と `_seed_demand` を再利用する。
Battery / Motor / ECU の各leaf→Yard→MOM、40週、商品SKU-A。
Backward→copy→Forwardの実処理を通し、人工条件はcopy後にメモリ内で設定する。
通常需要はindex 5 = **2024-W06**、Lot IDは `L05-00`。
Lot名の05をISO週番号とは読まない。

Observerは `_process_node` に渡る直前のPをコピー保存して、元の関数へ
そのまま委譲する。gate候補はdemand S、払出はYard S / actual_sとして記録する。
実出荷はplannerの `_actual_s` を診断目的で読む。新しい公開APIは導入しない。
JSONには6条件×7ノード×40週のP/S/I/CO、actual、期首残、demand S、
封印前P、kitting、能力イベントを記録する。

すべてsupply layerの組立・部材ノードの評価。末端販売・PPCの評価は今回含まない。
T03は期首在庫を直接指定するForward境界試験であり、CSVローダによる
期首在庫・注文残の設定可否を保証しない。

## 観測結果

| ケース | MOM P合計 | MOM実出荷合計 | 各Yard払出合計 | 各Yard期末I | MOM期末CO |
|---|---:|---:|---:|---:|---|
| T01 通常1需要 | 1 | 1 | 1 | 0 | 0 |
| T02 ECUのみ2週遅着 | 0 | 0 | 0 | 1 | L05-00が1件 |
| T03a 完成品期首Iあり、部材なし、当週要求 | 0 | 1 | 0 | 0 | 0 |
| T03b 完成品期首Iあり、同じIDの部材も供給 | 1 | 1 | 1 | 0 | 0 |
| T03c 完成品期首I＋期首CO、部材・新規組立要求なし | 0 | 1 | 0 | 0 | 0 |
| T04 2需要、W06組立hard能力1 | 1 | 1 | 2 | 0 | L05-01が2件 |

各Yardは部材ごとの1 setを保持する。3 Yardの同じIDを完成品3個と集計しない。
T03bのMOM期末Iは0。T03cのCOは当初週に1件記録され、同週実出荷で履行される。
過去COの記録が残ることは未履行を意味しない。

### T02：後日揃ってもgateが再処理しない

ECU leafの供給Pをindex 2から4へ移動。輸送LTは変更しない。
ECUはW08にYardへ到着し、他の2部材と同じIDが揃う。
しかしW08のMOM demand Sは空で、Pも実出荷も0。
W40まで3部材が各Yardに残り、MOMのCOにL05-00が残る。

MOM CO期間和は34 lot-週。固有未履行需要は1件であり、34注文ではない。
原因は `_process_assembly_with_yards` の候補が当週demand Sだけであること。
COは後段の `_process_node` で保持されるがgate候補へ戻されない。

### T03：既存完成品の引当と重複組立を区別

T03aとT03cでは、既存完成品を利用して1回出荷し、部材消費・追加生産は0。
とくにT03cはCO[0]に同じIDを置き、新規MOM Sを空にした期首境界試験。
通常のCO引当自体を全面的に作り直す根拠はない。

T03bでは期首完成品Lと、L用の部材供給・W06組立要求が共存する。
gateは完成品Iを見ないため部材を払い出してPへLを再生成する。
W06に「期首I 1＋P 1−actual 1−期末I 0＝1」の残差が生じる。
`_match_by_identity` は同じIDの供給複数件を、1回のmatchで残在庫から
すべて除くためである。

これは意図的な重複供給境界条件であり、通常サンプルに常時発生するとの主張ではない。
しかし完成品・要求・部材が共存した際、gateで再生産を抑止するか、
入力不整合として診断する条件の定義が必要。

### T04：部材払出後に完成Pが削られる

Backward/copy後にMOMのW06 cap_hard=1を設定。W06には2需要・全部材2 setがある。
cap=0は現行の無制限解釈と混同し得るため使用しない。

各Yardは2 setを払い出し、封印前MOM Pは2件。
その後 `_process_node` が1件をPから除去し、翌週COへ記録する。
需要照合も同じ未充足IDを翌週COへ追加するため、COにL05-01が2件残る。
MOM CO期間和68 lot-週、固有未履行需要1件、sealed 1。
この条件ではCOの重複は2件のまま継続し、毎週倍増したわけではない。

Yard単体の在庫式と、封印後Pを使ったMOM単体の在庫式はどちらも残差0。
しかし各部材2 set消費に対して完成計上は1件、残部材も0。
したがって、ノード単体の収支だけではCompositeの変換境界の欠落を検知できない。
新規加工中WIPを導入しない合意の下では、未成立分を部材として保持する設計が必要。

## 実モデルの既存確認

以下のCSV Integrationを基準コードで実行し **2 passed in 2.57s**。

```sh
python -m pytest -q tests/test_stage3a2_kitting_gate.py::test_bom_test_2026_vehicle_assy_p_matches_s tests/test_stage3a2_kitting_gate.py::test_ev_europe_2026_import_factory_p_matches_real_demand
```

これは既存BOM/EVモデルの正常条件の確認。遅着・能力不足の結果を
実モデルCSVで再現したと読み替えない。初回範囲でcore変更はないため、
前回済みの全golden掃引を追加反復していない。

## 詳細設計に渡す最小変更案（未実装）

1. 組立候補に未完了kitを持ち越す。出荷COを無条件に組立候補へ足さない。
2. 完成済み・履行済みIDを候補から外し、完成品引当を再生産より優先する。
3. その週に生産可能なkitを確定してから、各部材払出と完成P記録を一体で行う。
4. 能力待ちkitは部材Iと未完了要求として保持する。完成Pを後段で再度削らない。
5. 出荷要求の繰越は一つの処理が管理し、同じIDの封印由来COを重ねない。
6. 当週要求・過去未完了・完成済み・出荷済みを区別する週次遷移を具体化する。

設計上の注意: 現行gateはYardだけを全週計算した後にMOMの全週処理を呼ぶ。
そのため同週の完成品引当・COをgateに反映するには、週次処理の協調方法を
設計する必要がある。単なる候補集合追加だけで完了としない。

候補順序はまず既存需要順を尊重する案とし、能力競合時の旧要求優先などは
受入例で明示する。共有MOM処理の全面改変や新schemaは今回の実測から要求しない。

未実測: T05〜T10（Yard混在・期首部材、TW、OT、Buffer余裕、専用期末境界）等。
これらを今回の6条件で解決済みと扱わない。実装Request Letterには対象モード・
関数・互換性・試験範囲を明記し、core変更承認と独立レビューの手順を維持する。

## 再現

基準SHAのcheckoutに測定スクリプトを配置し、適合済みvenvで実行する。

```sh
python -m tools.probe_composite_baseline --out /tmp/composite_baseline_trace.json
```

スクリプトは基準SHAを照合する。結果は指定JSONに保存する。
原本CSVは編集せず、合成fixtureのメモリ内変更のみ。
実行後の追跡対象差分なしを確認し、追加は本報告と測定資料だけとする。


````
