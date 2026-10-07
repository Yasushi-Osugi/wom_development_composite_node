#!/usr/bin/env python3
"""Lossless ordered CSV range storage and full-data restoration (stdlib only).

No sampling, sorting, deduplication or numeric conversion. A range preserves
the first row's strings and increments only consecutive ID suffixes/sequence.
Restored UTF-8 CSV bytes must match the original uncompressed SHA-256.
Gzip container bytes are not promised identical across zlib implementations.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil

ID = re.compile(r"^(.*:)([0-9]+)$")


def sha(path, uncompressed=False):
    h=hashlib.sha256()
    opener=gzip.open if uncompressed and str(path).endswith(".gz") else open
    with opener(path,"rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()


def descriptors(header,row):
    fields=[]
    for i,(name,value) in enumerate(zip(header,row)):
        if name=="sequence" and value.isdigit():
            fields.append([i,"",int(value),0])
        elif name=="lot_id" or name.endswith("_lot_id"):
            m=ID.match(value)
            if m: fields.append([i,m[1],int(m[2]),len(m[2])])
    return fields


def expanded_row(first, fields, offset):
    row=list(first)
    for i,prefix,start,width in fields:
        row[i]=prefix+str(start+offset).zfill(width)
    return row


class DigestWriter:
    def __init__(self): self.h=hashlib.sha256()
    def write(self,value):
        self.h.update(value.encode("utf-8")); return len(value)


def encode(source,destination):
    source=Path(source); destination=Path(destination)
    opener=gzip.open if source.suffix==".gz" else open
    with opener(source,"rb") as f:
        line=f.readline(); newline="\r\n" if line.endswith(b"\r\n") else "\n"
    row_count=run_count=0; destination.parent.mkdir(parents=True,exist_ok=True)
    with opener(source,"rt",encoding="utf-8",newline="") as sf, \
         gzip.open(destination,"wt",encoding="utf-8",newline="\n") as df:
        reader=csv.reader(sf); header=next(reader)
        df.write(json.dumps({"format":"ordered_csv_ranges_v1","header":header,"lineterminator":newline},ensure_ascii=False)+"\n")
        first=None; fields=[]; count=0
        for row in reader:
            if len(row)!=len(header): raise ValueError("Nonrectangular CSV")
            row_count+=1
            if first is not None and row==expanded_row(first,fields,count):
                count+=1; continue
            if first is not None:
                df.write(json.dumps([count,first,fields],ensure_ascii=False,separators=(",",":"))+"\n"); run_count+=1
            first=row; fields=descriptors(header,row); count=1
        if first is not None:
            df.write(json.dumps([count,first,fields],ensure_ascii=False,separators=(",",":"))+"\n"); run_count+=1
    result={"original_bytes":source.stat().st_size,"encoded_bytes":destination.stat().st_size,
        "rows":row_count,"ranges":run_count,"original_container_sha256":sha(source),
        "csv_bytes_sha256":sha(source,uncompressed=True),"ranges_sha256":sha(destination)}
    check=restore(destination,None)
    if check["rows"]!=row_count or check["csv_bytes_sha256"]!=result["csv_bytes_sha256"]:
        raise AssertionError("Full ordered CSV restoration failed")
    result["full_restore_verified"]=True
    return result


def restore(source,destination=None):
    source=Path(source); sink=DigestWriter(); file_obj=None
    if destination is not None:
        destination=Path(destination)
        if destination.exists(): raise FileExistsError(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        opener=gzip.open if destination.suffix==".gz" else open
        file_obj=opener(destination,"wt",encoding="utf-8",newline="")
    count=0
    try:
        with gzip.open(source,"rt",encoding="utf-8") as f:
            meta=json.loads(next(f))
            if meta["format"]!="ordered_csv_ranges_v1": raise ValueError("Unknown format")
            hasher=csv.writer(sink,lineterminator=meta["lineterminator"])
            writer=csv.writer(file_obj,lineterminator=meta["lineterminator"]) if file_obj else None
            hasher.writerow(meta["header"])
            if writer: writer.writerow(meta["header"])
            for line in f:
                n,first,fields=json.loads(line)
                if n<1: raise ValueError("Invalid range length")
                for i in range(n):
                    row=expanded_row(first,fields,i); hasher.writerow(row)
                    if writer: writer.writerow(row)
                count+=n
    finally:
        if file_obj: file_obj.close()
    return {"rows":count,"csv_bytes_sha256":sink.h.hexdigest()}


def restore_bundle(root,destination=None):
    root=Path(root); index=json.loads((root/"RAW_FILE_INDEX.json").read_text(encoding="utf-8"))
    for entry in index["range_files"]:
        source=root/entry["stored_path"]
        if sha(source)!=entry["ranges_sha256"]: raise ValueError("Stored file checksum mismatch")
        target=Path(destination)/entry["original_path"] if destination else None
        check=restore(source,target)
        if check["rows"]!=entry["rows"] or check["csv_bytes_sha256"]!=entry["csv_bytes_sha256"]:
            raise ValueError("Restored CSV checksum mismatch")
        print("VERIFIED",entry["original_path"],check["rows"],flush=True)
    if destination:
        for entry in index["ordinary_files"]:
            source=root/entry["stored_path"]
            if sha(source)!=entry["sha256"]: raise ValueError("Ordinary file checksum mismatch")
            target=Path(destination)/entry["original_path"]
            if target.exists(): raise FileExistsError(target)
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-root",type=Path,required=True)
    p.add_argument("--destination",type=Path)
    args=p.parse_args(); restore_bundle(args.evidence_root,args.destination)


if __name__=="__main__": main()
