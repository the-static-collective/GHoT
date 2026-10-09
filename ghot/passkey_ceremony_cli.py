#!/usr/bin/env python3
"""Local ceremony operator for PostEmahh'n passkey tests. No hosted endpoint."""
import argparse
import json
from pathlib import Path
from postemahhn_mail import load_json, write_json
from postemahhn_passkey_door import (
    begin_enrollment, approve_enrollment, finish_enrollment,
    begin_assertion, verify_assertion,
)
from relatte_identity import IdentityKey

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("begin-register")
    a.add_argument("owner_public_json",type=Path)
    a.add_argument("rp")
    a.add_argument("origin")
    a.add_argument("store",type=Path)
    a.add_argument("out",type=Path)
    a=sub.add_parser("owner-approve-register")
    a.add_argument("ticket_json",type=Path)
    a.add_argument("owner_private_pem",type=Path)
    a.add_argument("out",type=Path)
    a=sub.add_parser("finish-register")
    a.add_argument("ticket_json",type=Path)
    a.add_argument("owner_approval_txt",type=Path)
    a.add_argument("browser_registration_json",type=Path)
    a.add_argument("store",type=Path)
    a.add_argument("out",type=Path)
    a=sub.add_parser("begin-print-check")
    a.add_argument("wallet_request_json",type=Path)
    a.add_argument("policy_json",type=Path)
    a.add_argument("station_public_json",type=Path)
    a.add_argument("credential_json",type=Path)
    a.add_argument("store",type=Path)
    a.add_argument("out",type=Path)
    a=sub.add_parser("verify-print-check")
    a.add_argument("ticket_json",type=Path)
    a.add_argument("wallet_request_json",type=Path)
    a.add_argument("policy_json",type=Path)
    a.add_argument("station_public_json",type=Path)
    a.add_argument("browser_assertion_json",type=Path)
    a.add_argument("store",type=Path)
    args=p.parse_args()
    if args.action=="begin-register":
        result=begin_enrollment(load_json(args.owner_public_json),args.rp,args.origin,args.store)
    elif args.action=="owner-approve-register":
        proof=approve_enrollment(load_json(args.ticket_json),IdentityKey(args.owner_private_pem))
        args.out.write_text(proof+"\n",encoding="ascii")
        print("local owner approval recorded")
        return
    elif args.action=="finish-register":
        result=finish_enrollment(args.store,load_json(args.ticket_json),
            args.owner_approval_txt.read_text(encoding="ascii").strip(),
            load_json(args.browser_registration_json))
    elif args.action=="begin-print-check":
        result=begin_assertion(args.store,load_json(args.wallet_request_json),
            load_json(args.policy_json),load_json(args.station_public_json),
            load_json(args.credential_json))
    else:
        result=verify_assertion(args.store,load_json(args.ticket_json),
            load_json(args.wallet_request_json),load_json(args.policy_json),
            load_json(args.station_public_json),load_json(args.browser_assertion_json))
        print(json.dumps(result,indent=2))
        return
    if args.out.exists():
        raise ValueError("output already exists")
    write_json(args.out,result)
    print(str(args.out))

if __name__=="__main__":
    main()
