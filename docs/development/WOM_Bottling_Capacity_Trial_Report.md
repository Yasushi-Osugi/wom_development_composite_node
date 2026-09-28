---
knowledge_id: WOM-CAPACITY-TRIAL-01
kind: evidence_report
status: documented_with_raw_evidence_gap
report_date: 2026-09-26
basis_sha: 4ed2f145dfb30b95058c0d274665eca64e4fc4c4
---
# Bottling_Noda capacity Trial：対象操作・週位置・診断・表示

## 1. 結論と資料の位置づけ

今回の対象では、**閉鎖週の入庫Pが正でも、同週の実出荷は0である。Pと実出荷を同じ処理量としてcapacityと比較してはいけない。** また、2027-W17の「予定S=686／実出荷=0」は再現したが、そのSに含まれる686 Lot_IDは全てW16に出荷済みだった。この事象をそのまま「686 Lotの遅配」「Forwardの封印が原因」と説明するのは不適切である。

一方、期間全体では実供給に到達しない需要が存在する。S3の「未充足0」は、下流の計画供給再設定を含むモデルの指標であり、上流から市場までの物理供給が全て成立したことを保証しない。

これは固定コミット・限定ケースのASIS報告であり、全ノードへの一般化や新しいcapacity仕様の承認ではない。core修正は提案・実施していない。

### 証拠の可用性に関する制約

前回の測定時に出力された数値、Lot_ID履歴、コード断片、pytest結果を、本セッションの実行記録から整理した。2026-09-26の再開時には、前回の独立作業コピー、CSV/JSON生トレース、測定スクリプトが実行環境に残っていなかった。

したがって、本書は**記録に基づく正本報告**であるが、第三者が付属生データで再集計できる完全な証拠パッケージではない。消失したCSV/JSONを再生成したかのように扱わない。本再開では追加測定・再テストを行っていない。生証拠の再取得は、必要になった際の別作業とする。

## 2. 目的・範囲・終了条件

目的は、Vaultの関係「能力とLTが同期可能性を制約する」を入口に、対象操作・週位置・実装・診断・表示を対応づけ、確認事実を知識へ戻すこと。

| 項目 | 固定した範囲 |
|---|---|
| リポジトリ | Yasushi-Osugi/wom_development_composite_node |
| ブランチ | wom-v1r5m0 |
| 測定基準 | 4ed2f145dfb30b95058c0d274665eca64e4fc4c4 |
| 主対象 | soysauce-jpy-2027-alloc / Soy_Sauce / Bottling_Noda |
| 主条件 | s1_base、P_opt、cap_wk=800 |
| 対照 | 同モデルの原需要、soysauce-jpy-2027の原需要 |
| 期間 | 各130週：2026-W28～2028-W52 |
| 実行 | 独立Linuxコピー、HeadlessとS3の純粋View Model |
| 対象外 | core改修、他モデル、新しい能力変更実験、Windows GUI最終確認、golden更新、commit/push |

終了条件は、本対応の説明、修正候補と未確認事項の分離、正本MarkdownとVault参照追記の提出。今回の資料提出で作業を終了し、調査を自動的に延長しない。

## 3. 測定方法と検証記録

前回実行ではモデルを一時コピーし、実際のHeadless処理を呼び出した。観測ラッパーは元メソッドに処理を委譲し、Backward後、copy後、push setup後、Bottling処理直前、Forward後を記録した。P_opt条件では配分計算から需要生成、run_s3、build_s3_viewまで実行した。

実行記録によれば、3条件とも観測あり／なしのHeadlessスナップショットが一致し、P_opt条件のS3 Viewも一致した。元モデルのファイルハッシュ一致と既存追跡ファイルの差分なしを確認した。新規probeとVault追記用スクリプトのみ作成し、commit/pushは行わなかった。これらスクリプト自体は本書に同梱できていない。

| 確認 | 前回記録 |
|---|---|
| Git整合性 | fsck --full 成功 |
| 既知コードとの比較 | 7d6c7d7から基準HEADまでのwom/tools/tests/data/AGENTS.mdに差分なし |
| 依存関係 | Python 3.12.14、pandas 3.0.6、numpy 2.5.3、pytest 9.1.1、pip check成功 |
| golden＋基本capacity | 20 passed（golden 13件、test_step7_capacity 7件） |
| soft／操業／閉鎖関連 | 18 passed |
| Windows GUI | 今回は未実施 |

最初のpytest呼出しはリポジトリ外を作業ディレクトリにしてしまい、PPCの相対fallbackパスを解決できず3 failed / 17 passedだった。リポジトリ直下で再実行すると20 passedとなった。期待値やgoldenを書き換えて解消したものではない。Linux仮想環境は欠けていたPython実行リンクを復元して使用した。

38件の成功は測定基盤と既存挙動の確認であり、capacityの業務意味やE2E物理整合性が全て正しいことの証明ではない。

## 4. 対象操作・週位置・実装の対応

| 段階 | 実装が扱う対象 | 週の意味・確認した挙動 |
|---|---|---|
| capacity CSV | ノード別max_supply | -allocのBottling hard=800 lot/週 |
| 操業カレンダー | 直数からsoftを算出 | 18直、MAX_SHIFTS=21からround(18×800/21)=686 |
| Holiday PRE_PLAN | 閉鎖週capacityとexplicit_closures | W18のhardを0.1へ設定。同呼出しのset_capacityの既定引数によりsoftは0になる |
| Backward | MOMの需要Sを平準化 | Bottlingはdemand_envelope=soft。通常週686、閉鎖週S=0。需要を前週へ繰り戻す |
| Demand→Supply copy | 計画リストの複写 | Supply Sは需要の週別要求を保持。copy時Pは後続Forwardの最終入庫ではない |
| Mode 4 setup | MaterialsのPを再配置 | Bottling Demand SのLot_IDを7週前に配置。需要IDを新造しない |
| 上流Forward | 実出荷を親Pへ伝播 | Materialsから2週、Brewingから4週。計6週でBottling Pに到着 |
| Bottling Forward | pushノードの入庫・在庫・出荷 | Pは上流からの入庫。利用可能量から週のS件数まで出荷する。ID照合ではなくリスト先頭から取り出す |
| hard診断 | push以外のP封印 | Bottlingはpushなので封印をskip。BottlingにS/実出荷のhard封印が実装されたことにはならない |
| soft診断 | Pとsoftの比較 | pushもPを比較する。S3の実出荷系列と同じ観測対象ではない |
| S3の棒 | pushではS件数−shortfall | 対象130週すべてで内部actual_s件数と一致 |
| S3の能力判定 | Forwardのhard/softイベント | 棒とcapacityを再比較して算出するものではない。Backward envelopeも結論行の集合には入らない |

**今回の実測ではsoft超過イベントは0件。** hardのskipとsoftの継続比較という非対称性だけで、softのコードが誤りとは断定しない。hard/softが同じ操作を制約すべきなのか、別の運用負荷を表すのか、業務契約の明文化が先である。

なお、Backward PとSが全期間で常に同一という一般化もしない。P_opt測定ではDemand P合計77,518、Demand S合計78,709だった。以下の週別説明は実際に観測した週に限定する。

## 5. 主要数値

### 5.1 条件別の全期間集計

| 条件 | Bottling S合計 | P合計 | 実出荷合計 | 同週数量shortfall合計 | I期間和 |
|---|---:|---:|---:|---:|---:|
| jpy原需要 | 100,501 | 100,501 | 100,501 | 0 | 100,501 |
| alloc原需要 | 80,093 | 75,291 | 75,291 | 4,802 | 50,595 |
| alloc P_opt / 800 | 78,709 | 73,907 | 73,907 | 4,802 | 49,211 |

S・P・実出荷は期間内の件数合計。I期間和はlot-週であり、期末在庫でも固有Lot数でもない。3条件とも、Bottling実出荷が正のhard/softを超えた週は0。Pがhardを超える週は2027-W18と2028-W18の2週だった。

### 5.2 P_opt条件の週別値

| 週 | hard | soft | P入庫 | S要求 | 実出荷 | 期末I | 同週shortfall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2027-W16 | 800 | 686 | 686 | 686 | 686 | 0 | 0 |
| 2027-W17 | 800 | 686 | 0 | 686 | 0 | 0 | 686 |
| 2027-W18 | 0.1 | 0 | 686 | 0 | 0 | 686 | 0 |
| 2027-W19 | 800 | 686 | 686 | 686 | 686 | 686 | 0 |
| 2028-W17 | 800 | 686 | 0 | 686 | 686 | 0 | 0 |
| 2028-W18 | 0.1 | 0 | 686 | 0 | 0 | 686 | 0 |

W18はHoliday適用前にはhard=800、soft=686、適用後はhard=0.1、soft=0。0.1は「通常能力の10%」として解釈していない。現行コードの整数化ではint(0.1)=0だが、Bottling pushにはhard封印自体が適用されない。

### 5.3 W17のLot_IDを追うと説明が変わる

W17のSに含まれる**686 Lot_ID全てがW16に実出荷済み**。代表例は `Soy_Sauce:US_W:2027-W30:00001`。

| 記録 | 週 |
|---|---|
| Bottling Demand S／P | 2027-W17 |
| BackwardのMaterials Demand P | 2027-W11 |
| Mode 4後のMaterials Supply P／実出荷 | 2027-W10 |
| Brewing P／実出荷 | 2027-W12 |
| Bottling P／実出荷 | 2027-W16 |
| SP_Soy実出荷 | 2027-W17 |
| Rest_US_West実出荷 | 2027-W30 |

Mode 4はBottling Sの要求週dから7週前にMaterials Pを置く。実伝播は2＋4=6週なので、Bottling Pはd−1に来る。W18のS=0に対応する入庫の空白がW17に現れる。W17時点では在庫も0であり、同週数量shortfallは686となる。

ただし、同じIDの要求が遅配になったのではなく、先行週の数量枠で既に出荷されていた。2028-W17では在庫が空白を埋め、同週実出荷686となった。

閉鎖を「入庫禁止」と読むか「瓶詰・出荷操作の停止」と読むかの業務定義は別問題として残る。今回の事実だけからPを閉鎖週に封印する修正を行う根拠にはならない。

### 5.4 同週不足とID未達は別の集合

P_optの同週shortfall4,802は、2026-W28～W33の6週と2027-W17の1週に、それぞれ686として現れた。

一方、Bottling SのID別追跡で一度も実出荷されない4,802 Lotは、2026-W28～W34の7週の要求だった。Mode 4の7週前倒しが期間外となる先頭7週に対応する。**合計が一致しても、不足が属する週・IDは同一ではない。** W34は同週shortfall=0だが、そのSの686 IDは実出荷されず、後の週を要求週とするIDが出荷されている。

Bottling SのID分類は、早出し24,696、同週49,211、後日0、期間内未出荷4,802。観測したBottling actual_sに同一IDの重複出荷はなかった。この分類は「Bottlingでの要求週との比較」であり、市場での納期充足とは区別する。

## 6. 診断と表示の読み方

### 能力表示

P_optのS3結論行は次のとおりだった。

> 130 週中 130 週は能力内（100%）
>
> 能力超過なし（cap_hard 0週 / cap_soft 0週）、未充足 0 lot

今回の実出荷がhard/softを超えないことは測定でも確認した。ただし、この文章の生成根拠はForwardイベントの不在であり、「push出荷をhardで制限した結果」の証明ではない。

`build_capacity_load_report()`はPを評価するため、同じW18をover_hard=True、hard_util=6860として返した。S3は実出荷0を描き、イベントなしとする。比較対象の異なる診断を同じ「能力超過」と扱えば誤解を生む。今回のprobeはこの関数を別途呼んで比較したもので、S3がこのレポートを直接使うという意味ではない。

### 未充足表示とE2E供給

P_optの市場需要は83,200 Lot。BottlingでBackwardの期間前へ繰り戻された記録は4,491件、残るSは78,709。そこからMode 4の期間端で4,802 IDが実供給に到達せず、Bottling実出荷は73,907だった。

| ノード | S期間合計 | 実出荷期間合計 | 最終週CO |
|---|---:|---:|---:|
| Bottling_Noda | 78,709 | 73,907 | 0 |
| SP_Soy | 83,200 | 73,907 | 9,293 |
| FG_WH_Noda | 83,200 | 73,907 | 9,293 |
| DC_US_SF | 17,588 | 17,588 | 0 |
| Rest_US_West | 17,588 | 17,588 | 0 |

9,293＝4,491＋4,802。各ノードのCOを足して固有不足Lot数としない。またCO期間和を期末注文残と取り違えない。

OT側のdecouple以降は、子のPをDemand Pで再設定する計画経路を持つ。このため下流のleaf指標は上流の供給不足をそのまま継承しない。`attach_realized()`の未充足はleaf CO集計であり、今回0となった。PPCのlot数も83,200である。これは今回のモデル境界として説明できるが、E2E物理実現を評価したい場合に、このままでよいかは仕様判断が必要となる。

## 7. 修正候補と未確認事項

| 分類 | 対象 | 今回の判断・次の扱い |
|---|---|---|
| 説明修正が必要 | W17を封印起因の686 Lot遅配と説明すること | 同週数量差とID早出しを分けて記載する。Request Letterの関連説明も次回レビュー対象 |
| 表示説明の改善候補 | 「130/130能力内」 | 判定元がForwardイベントであること、pushのhard封印対象外を説明できる表現にする |
| 診断契約の明文化 | soft=P、S3=actual、load_report=P | 各々の操作・週・単位を明記。同じ対象だと決めるまでは判定式の統一をしない |
| 業務判断 | 閉鎖週の受入れ可否 | 瓶詰・出荷停止と入庫停止を区別して決定。P>hardだけで修正しない |
| 業務判断 | pushの早出しとCO非連鎖 | 現行の件数制御・在庫払出しを許容するか。今回後追い出荷を追加しない |
| 別Trial候補 | E2E物理供給と下流計画供給 | S3／PPCがどちらを評価すべきか定義する。今回の改修範囲には広げない |
| 未確認 | 別条件で実出荷がcapacityを超える場合 | 今回3条件は超過なし。汎用的な保証は未認定 |
| 未確認 | Windows GUI | 純粋View Modelの値は測定したが画面の最終受入れは未実施 |
| 証拠不足 | CSV/JSON／probe原本の再配布 | 今回の環境には残っていない。再測定は行わず制約として保持 |

## 8. 固定コミットの根拠入口

リンクは前回調査した固定コミットのソース位置を示す。今回再開時の再取得・最新HEAD調査は行っていない。

- [capacity_sealer.py：容量ロード、直数からsoft、P負荷レポート](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/engine/capacity_sealer.py)
- [holiday_calendar_plugin.py：on_pre_plan、_apply_supply_closure](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/engine/holiday_calendar_plugin.py)
- [plan_node.py：set_capacityのhard/soft既定値](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/model/plan_node.py)
- [backward_planner.py：_apply_mom_cap_backward、_offset_week](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/engine/backward_planner.py)
- [push_pull.py：Mode 4のWHO維持／WHEN再配置](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/engine/push_pull.py)
- [forward_planner.py：_process_node、_propagate_to_parent、_push_pull_node](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/engine/forward_planner.py)
- [run_headless_from_folder.py：_planning_state_extras](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/tools/run_headless_from_folder.py)
- [s3_view_model.py：run_s3、_capacity_nodes、_format_conclusion_ja](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/cockpit/s3_view_model.py)
- [planning_state：attach_realized](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/wom/planning_state/__init__.py)
- [Phase8-3c-4 Request Letter](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/4ed2f145dfb30b95058c0d274665eca64e4fc4c4/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md)

S3の実出荷表示はcommit `1bd6c44` のRequest Letter付き実装で確認された。後続`7d6c7d7`はKitting回復の実装。本Trialはその既存挙動の調査であり、新しい実装コミットではない。

## 9. Vaultへ戻す追記と配置

今回はownerのVaultを直接変更していない。以下の手動配置で正本を一つに保ち、既存ノートの末尾から参照できる。ファイル名を変えず、本書をVault内の `50_Trials/WOM_Bottling_Capacity_Trial_Report.md` に置く。まずはこのファイルを唯一の編集正本とする。Git管理へ移す際は正本の置き場所を決め、Vault版とrepository版を別々に編集しない。

### 追記対象

- `30_Relations/R10 能力とLTが同期可能性を制約する.md`
- `30_Relations/R03 供給結果を需要要求と照合する.md`
- `20_Concepts/C14 能力・LT・操業条件.md`
- Q1（Demand LayerとSupply Layer）、Q4（二つのPSI List）、Q7（消費の加速・減速）

既存内容は残し、次の短い節を末尾に追記する。同じ節が既にある場合は重複追加しない。

```markdown
## Bottling_Noda：対象限定のTrial追補（2026-09-26）

[[50_Trials/WOM_Bottling_Capacity_Trial_Report|対象操作・週位置・診断・表示の確認結果]]

capacityの対象と表示系列を区別し、同週数量差とLot_IDの早出し・未充足を照合した。
固定SHA・醤油3条件の実行記録に基づく。生トレース再配布には制約があり、
全ノードへの一般化やcore変更の承認を意味しない。
```

R10のASIS欄には、必要に応じて次の一文を追記できる。

> Bottling_Nodaの限定Trialでは、Mode 4の7週前倒しと6週の伝播が入庫の週位置を決め、同週のS−actualだけではID未充足を判定できないことを確認した。根拠と適用限界はTrial正本を参照する。

## 10. 今回の終了判定

- 対象操作・週位置・実装・診断・表示の対応：本書に整理済み。
- 同週数量差とID単位の早出し／未充足：区別して記録済み。
- 修正候補と未確認事項：第7節に分離済み。
- 正本とVault追記：本書で提出。owner環境への配置は未実施。
- 生データ付きの独立再検証：証拠ファイル不在のため未達。本書でその制約を明記。

**今回の再開作業は、既存実行記録を知識へ戻す資料の提出で終了する。生証拠の補完や実装変更へは自動的に進まない。**
