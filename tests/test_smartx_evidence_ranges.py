"""Evidence must preserve ordering, multiplicity, strings and CSV bytes."""
import csv
import gzip
import pytest
from tools.smartx_evidence_ranges import encode,restore,sha


@pytest.mark.parametrize("newline",["\n","\r\n"])
def test_full_bytes_roundtrip_with_duplicates_and_discontinuous_ids(tmp_path,newline):
    source=tmp_path/"source.csv.gz"; ranges=tmp_path/"ranges.jsonl.gz"; recovered=tmp_path/"recovered.csv.gz"
    rows=[
        ["a", "0", "SKU:R:2027-W01:00001", "", "comma,quoted"],
        ["a", "1", "SKU:R:2027-W01:00002", "", "comma,quoted"],
        ["a", "2", "SKU:R:2027-W01:00002", "", "comma,quoted"],
        ["a", "3", "SKU:R:2027-W01:00008", "", "a\nnew line"],
        ["b", "0", "SKU:R:2027-W02:99999", "X:00001", "001.0"],
        ["b", "1", "SKU:R:2027-W02:100000", "X:00002", "001.0"],
    ]
    with gzip.open(source,"wt",encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator=newline);w.writerow(["group","sequence","lot_id","csv_lot_id","value"]);w.writerows(rows)
    info=encode(source,ranges); assert info["rows"]==6 and info["ranges"]<6
    got=restore(ranges,recovered)
    assert got["csv_bytes_sha256"]==sha(source,True)==sha(recovered,True)
    with gzip.open(recovered,"rt",newline="") as f: assert list(csv.reader(f))[1:]==rows


def test_header_only_is_preserved_and_overwrites_are_refused(tmp_path):
    source=tmp_path/"empty.csv"; source.write_bytes(b"lot_id,status\r\n")
    stored=tmp_path/"empty.ranges.gz"
    assert encode(source,stored)["rows"]==0
    with pytest.raises(FileExistsError): restore(stored,source)
