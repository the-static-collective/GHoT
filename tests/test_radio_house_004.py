"""RADIO HOUSE 004 — genuine HTTP loopback, owner clicks, separately keyed endpoints."""
import copy
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ghot.radio_house_002 import favorable_lab_power, connect, enable, observe_media
from ghot.radio_house_003 import make_bundle, verify_return, digest
from ghot.radio_house_004 import Worker, _server, initialize, load_identity, actual_gate, MAX_BODY
from ghot.relatte_identity import IdentityKey

def clear():
    return {"status":"NO_KNOWN_CAPTURE_PROCESS","processes":[]}

def blocked():
    return {"status":"CAPTURE_PROCESS_PRESENT_HOLD","processes":["obs"]}

def req(url,obj=None,headers=None):
    payload=None if obj is None else json.dumps(obj).encode()
    r=urllib.request.Request(url,data=payload,headers=(
        {"Content-Type":"application/json",**(headers or {})} if payload is not None else (headers or {})),
        method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(r,timeout=4) as x:
            raw=x.read()
            if "text/html" in x.headers.get("Content-Type",""):
                return x.status,raw.decode()
            return x.status,json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read())

def fixture(folder):
    root=Path(folder); sender=root/"sender"; worker=root/"worker"
    info=initialize(sender,"requester")
    pin=root/"sender-pin.json";pin.write_text(json.dumps(info["public_key"]))
    rock=initialize(worker,"worker",requester_pin=pin)
    return sender,worker,info,rock

class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.sender,self.root,self.source,self.worker_id=fixture(self.tmp.name)
        self.worker=Worker(self.root,power_provider=favorable_lab_power,obs_provider=clear)
        self.admin=_server(self.worker,0,"admin")
        self.intake=_server(self.worker,0,"intake")
        self.a="http://127.0.0.1:"+str(self.admin.server_port)
        self.i="http://127.0.0.1:"+str(self.intake.server_port)
        self.threads=[]
        for server in [self.admin,self.intake]:
            t=threading.Thread(target=server.serve_forever,daemon=True)
            t.start();self.threads.append(t)
        self.signer=load_identity(self.sender,"requester")
    def tearDown(self):
        for s in [self.admin,self.intake]:s.shutdown();s.server_close()
        for t in self.threads:t.join(timeout=2)
        self.tmp.cleanup()
    def bundle(self,text="Public synthetic input. "*40,at=None):
        return make_bundle(self.signer,self.worker_id["public_key"],"public-test-001",
                           text,at=int(time.time()) if at is None else at,lifetime=800)
    def click(self,act,obj=None,headers=None):
        hdr={"Origin":self.a,"X-Radio-House-Token":self.worker.admin_token}
        if headers:hdr.update(headers)
        return req(self.a+"/api/"+act,{} if obj is None else obj,hdr)
    def permit(self):
        self.assertEqual(self.click("enable")[0],200)
        self.assertEqual(self.click("media",{"mode":"IDLE_CONFIRMED"})[0],200)
    def push(self,b):
        return req(self.i+"/intake",b)
    def test_click_console_is_real_page_and_private_side_only(self):
        code,html=req(self.a+"/")
        self.assertEqual(code,200)
        self.assertIn("Confirm idle",html)
        self.assertIn("Step ×10",html)
        self.assertIn(self.worker.admin_token,html)
        self.assertEqual(req(self.i+"/")[0],404)
    def test_no_optin_hold_by_default(self):
        s=req(self.a+"/api/status")[1]
        self.assertFalse(s["opted_in"])
        self.assertEqual(s["gate"]["status"],"HOLD")
    def test_origin_token_and_host_guard(self):
        self.assertEqual(self.click("enable",headers={"Origin":"http://evil.test"})[0],400)
        self.assertEqual(self.click("enable",headers={"X-Radio-House-Token":"bad"})[0],400)
        self.assertEqual(req(self.a+"/api/status",headers={"Host":"evil.test"})[0],403)
        self.assertEqual(req(self.i+"/health",headers={"Host":"evil.test"})[0],403)
    def test_remote_intake_has_no_admin_permission(self):
        for path in ["/api/enable","/api/approve","/api/step","/api/status"]:
            self.assertEqual(req(self.i+path,{} if path!="/api/status" else None)[0],404)
        self.assertEqual(req(self.i+"/health")[1]["operator_authority"],"NONE")
    def test_unsigned_and_tampered_packets_refused(self):
        self.assertEqual(self.push({"execute":"shell"})[0],400)
        b=self.bundle();b["payload"]["text"]="changed"
        self.assertEqual(self.push(b)[0],400)
        self.assertEqual(req(self.a+"/api/status")[1]["inbox"],[])
    def test_wrong_source_worker_and_expiry_refused(self):
        stranger=IdentityKey.load_or_create(Path(self.tmp.name)/"stranger"/"key.pem")
        wrong=make_bundle(stranger,self.worker_id["public_key"],"alien-1","public",at=int(time.time()))
        self.assertEqual(self.push(wrong)[0],400)
        b=make_bundle(self.signer,stranger.public_jwk(),"alien-2","public",at=int(time.time()))
        self.assertEqual(self.push(b)[0],400)
        self.assertEqual(self.push(self.bundle(at=int(time.time())-1200))[0],409)
    def test_signed_packet_is_only_pending_not_execution(self):
        b=self.bundle()
        code,result=self.push(b)
        self.assertEqual(code,200)
        self.assertEqual(result["disposition"],"PENDING")
        self.assertEqual(req(self.i+"/result",{"bundle":b})[1]["state"],"PENDING")
        self.assertEqual(req(self.a+"/api/status")[1]["inbox"][0]["cursor"],0)
    def test_approve_require_explicit_owner_idle_and_power(self):
        b=self.bundle()
        self.push(b)
        cid=b["crossing"]["crossing_id"]
        self.assertEqual(self.click("approve",{"crossing_id":cid})[0],409)
        self.permit()
        self.assertEqual(self.click("approve",{"crossing_id":cid})[0],200)
        self.assertEqual(req(self.a+"/api/status")[1]["inbox"][0]["state"],"ADMITTED")
    def test_signed_completion_and_recomputed_return(self):
        b=self.bundle(text="tiny public text")
        cid=b["crossing"]["crossing_id"]
        self.push(b);self.permit()
        self.click("approve",{"crossing_id":cid})
        code,out=self.click("step",{"crossing_id":cid})
        self.assertEqual((code,out["state"]),(200,"COMPLETE"))
        result=req(self.i+"/result",{"bundle":b})[1]
        self.assertTrue(result["result_ready"])
        self.assertEqual(result["final"]["post_state_ref"],digest(b"tiny public text"))
        proved=verify_return(b,result["admission"],result["final"],
                             pinned_requester_public=self.source["public_key"],
                             pinned_worker_public=self.worker_id["public_key"],at=int(time.time()))
        self.assertEqual(proved["status"],"SIGNED_CROSSING_AND_LOCAL_HASH_RETURN_VERIFIED")
    def test_recording_withdraws_work_then_resume(self):
        b=self.bundle(text="public long "*100)
        cid=b["crossing"]["crossing_id"]
        self.push(b);self.permit();self.click("approve",{"crossing_id":cid})
        first=self.click("step",{"crossing_id":cid})[1]
        self.assertEqual(first["cursor"],256)
        self.click("media",{"mode":"RECORDING"})
        self.assertEqual(self.click("step",{"crossing_id":cid})[0],409)
        self.assertEqual(req(self.a+"/api/status")[1]["inbox"][0]["cursor"],256)
        self.click("media",{"mode":"IDLE_CONFIRMED"})
        self.assertEqual(self.click("step",{"crossing_id":cid,"steps":10})[1]["state"],"COMPLETE")
    def test_optout_cancels_and_prevents_more_work(self):
        b=self.bundle(text="public long "*100)
        cid=b["crossing"]["crossing_id"]
        self.push(b);self.permit();self.click("approve",{"crossing_id":cid})
        self.click("disable")
        self.assertEqual(self.click("step",{"crossing_id":cid})[0],409)
        self.assertEqual(self.click("cancel",{"crossing_id":cid})[1]["state"],"CANCELLED")
    def test_duplicate_transport_cannot_enqueue_twice(self):
        b=self.bundle()
        self.assertEqual(self.push(b)[1]["disposition"],"PENDING")
        self.assertEqual(self.push(b)[1]["disposition"],"PENDING")
        self.permit()
        self.click("approve",{"crossing_id":b["crossing"]["crossing_id"]})
        self.assertEqual(self.push(b)[1]["disposition"],"ADMITTED")
        self.assertEqual(len(req(self.a+"/api/status")[1]["inbox"]),1)
    def test_extra_control_fields_refused(self):
        self.assertEqual(self.click("enable",{"station_authority":"true"})[0],400)
        self.assertEqual(self.click("media",{"mode":"IDLE_CONFIRMED","broadcast":True})[0],400)
        self.assertEqual(self.push([])[0],400)
    def test_obs_process_guard_is_stronger_than_manual_idle(self):
        conn=connect(self.root)
        try:
            enable(conn,True)
            observe_media(conn,"IDLE_CONFIRMED")
            gate,_=actual_gate(conn,favorable_lab_power,blocked)
            self.assertEqual(gate["status"],"HOLD")
        finally:conn.close()
    def test_console_never_claims_station_or_media_authority(self):
        s=req(self.a+"/api/status")[1]
        self.assertFalse(s["real_station_adoption"])
        self.assertFalse(s["remote_shell_enabled"])
        self.assertEqual(s["actual_broadcasts"],0)
    def test_content_length_limit_before_request_body(self):
        with socket.create_connection(("127.0.0.1",self.intake.server_port),timeout=3) as s:
            request=("POST /intake HTTP/1.1\r\nHost: 127.0.0.1:"+
                     str(self.intake.server_port)+"\r\nContent-Type: application/json\r\n"+
                     "Content-Length: "+str(MAX_BODY+1)+"\r\n\r\n")
            s.sendall(request.encode())
            self.assertIn(b"413",s.recv(200))

class TwoProcessTest(unittest.TestCase):
    def test_two_operating_system_processes_and_real_http_signed_return(self):
        with tempfile.TemporaryDirectory() as home:
            sender,worker,source,recipient=fixture(home)
            def port():
                with socket.socket() as s:
                    s.bind(("127.0.0.1",0))
                    return s.getsockname()[1]
            ap,ip=port(),port()
            while ip==ap:ip=port()
            program=("import sys;from ghot.radio_house_004 import serve;"
                     "from ghot.radio_house_002 import favorable_lab_power;"
                     "serve(sys.argv[1],admin_port=int(sys.argv[2]),"
                     "intake_port=int(sys.argv[3]),power_provider=favorable_lab_power,"
                     "obs_provider=lambda:{'status':'NO_KNOWN_CAPTURE_PROCESS','processes':[]})")
            proc=subprocess.Popen([sys.executable,"-u","-c",program,str(worker),str(ap),str(ip)],
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            admin="http://127.0.0.1:"+str(ap);intake="http://127.0.0.1:"+str(ip)
            try:
                connected=False
                for _ in range(80):
                    try:
                        if req(intake+"/health")[0]==200:
                            connected=True;break
                    except (ConnectionError,OSError,urllib.error.URLError):
                        time.sleep(.05)
                self.assertTrue(connected,"independent worker did not start")
                _,page=req(admin+"/")
                token=re.search('const TOKEN="([^"]+)"',page).group(1)
                pin=Path(home)/"worker-pin.json"
                pin.write_text(json.dumps(recipient["public_key"]))
                cp=subprocess.run([sys.executable,"-m","ghot.radio_house_004","send",
                         "--root",str(sender),"--worker-pin",str(pin),
                         "--job-id","separate-process-001","--text","Public local network job",
                         "--port",str(ip)],capture_output=True,text=True,timeout=9)
                self.assertEqual(cp.returncode,0,cp.stderr)
                cid=json.loads(cp.stdout)["crossing_id"]
                self.assertEqual(req(intake+"/api/approve",{})[0],404)
                def click(action,body):
                    return req(admin+"/api/"+action,body,{"Origin":admin,
                                               "X-Radio-House-Token":token})
                self.assertEqual(click("enable",{})[0],200)
                self.assertEqual(click("media",{"mode":"IDLE_CONFIRMED"})[0],200)
                approved=click("approve",{"crossing_id":cid})
                self.assertEqual(approved[0],200,approved)
                self.assertEqual(click("step",{"crossing_id":cid})[1]["state"],"COMPLETE")
                bundle=sender/"outbox"/(cid.replace(":","_")+".json")
                ret=subprocess.run([sys.executable,"-m","ghot.radio_house_004","poll",
                           "--root",str(sender),"--worker-pin",str(pin),
                           "--bundle",str(bundle),"--port",str(ip)],
                           capture_output=True,text=True,timeout=12)
                self.assertEqual(ret.returncode,0,ret.stderr)
                result=json.loads(ret.stdout)
                self.assertEqual(result["status"],"SIGNED_CROSSING_AND_LOCAL_HASH_RETURN_VERIFIED")
                self.assertEqual(result["actual_media_actions"],0)
                self.assertTrue((sender/"received"/(cid.replace(":","_")+"-verified.json")).exists())
            finally:
                proc.terminate()
                try:proc.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.communicate(timeout=2)

if __name__=="__main__":
    unittest.main()
