"""Repeated durable handoff faults; engine hidden-spawn acceptance is separate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.ownership import Ownership
from lostzone.transfers import Transfers


def uid():
    return uuid.uuid4().hex


class TransferStressTest(unittest.TestCase):
    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=123, seed=456, monotonic=lambda:0, wall=lambda:1_800_000_000_000_000_000)
        self.ownership = Ownership(self.world)
        self.transfers = Transfers(self.world, b"stress-key"*4)

    def fingerprint(self):
        # Bounded live registry/ledger plus journal and command high water,
        # rather than copying all historical transfer checkpoint blobs.
        return (
            tuple(tuple(r) for r in self.store.db.execute("SELECT * FROM entity ORDER BY id")),
            tuple(tuple(r) for r in self.store.db.execute("SELECT * FROM item ORDER BY id")),
            tuple(tuple(r) for r in self.store.db.execute("SELECT * FROM player_session ORDER BY character_id")),
            tuple(tuple(r) for r in self.store.db.execute("SELECT * FROM character ORDER BY id")),
            tuple(self.store.db.execute("SELECT revision,event_highwater FROM world").fetchone()),
            tuple(self.store.db.execute("SELECT COUNT(*),MAX(sequence) FROM world_event").fetchone()),
            self.store.db.execute("SELECT COUNT(*) FROM command_result").fetchone()[0],
            tuple(tuple(r) for r in self.store.db.execute("SELECT id,state,target_owner,target_fence FROM transfer ORDER BY id")),
        )

    def fault(self, event_type, invoke):
        before, original = self.fingerprint(), self.store.event
        def interrupted(tx, aggregate, kind, *args, **kwargs):
            result = original(tx, aggregate, kind, *args, **kwargs)
            if kind == event_type:
                raise RuntimeError("injected after durable state and journal writes")
            return result
        with patch.object(self.store, "event", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError,"injected"):
                invoke()
        self.assertEqual(self.fingerprint(),before)
        self.assertFalse(self.store.db.in_transaction)

    def test_1000_player_and_group_handoffs_keep_one_registry_and_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            self.path = Path(folder)/"world.db"
            self.open()
            try:
                fences = {"cordon":self.world.claim_location("a",uid(),"cordon")["fence"],
                          "garbage":self.world.claim_location("b",uid(),"garbage")["fence"]}
                actors = {"cordon":"a","garbage":"b"}
                player, group, npc, mutant, casualty = [uid() for _ in range(5)]
                states = {player:{"health":.31,"money":500,"tasks":["return_to_camp"],"pstor":{"known":"тайник"}},
                          npc:{"health":.72,"wounds":["leg"],"money":1200,"relation":"friend"},
                          mutant:{"health":.61,"species":"dog","hunger":.23},
                          casualty:{"health":.2,"species":"dog"},
                          group:{"member_ids":[npc,mutant,casualty],"route":"patrol","losses":1}}
                for entity, kind in ((player,"CHARACTER"),(npc,"NPC"),(mutant,"MUTANT"),(casualty,"MUTANT"),(group,"GROUP")):
                    options = {"account":"stress-player"} if kind=="CHARACTER" else {}
                    self.ownership.create_entity("a",uid(),entity,kind,"cordon",fences["cordon"],states[entity],**options)
                for holder,kind in ((player,"PLAYER"),(npc,"NPC"),(casualty,"NPC")):
                    self.ownership.create_item("a",uid(),uid(),"wpn_ak74","cordon",fences["cordon"],kind,holder,
                                               quantity=2,state={"condition":.62,"ammo":17,"attachments":["scope"],"serial":"тот же"})
                self.ownership.kill("a",uid(),casualty,fences["cordon"],1,"combat")
                initial_items = [tuple(r) for r in self.store.db.execute("SELECT * FROM item ORDER BY id")]
                initial_states = {r["id"]:r["state"] for r in self.store.db.execute("SELECT id,state FROM entity")}
                locations = {player:"cordon",group:"cordon"}
                for index in range(1000):
                    entity = player if index%2==0 else group
                    source = locations[entity]
                    target = "garbage" if source=="cordon" else "cordon"
                    actor, recipient = actors[source], actors[target]
                    version = self.store.db.execute("SELECT version FROM entity WHERE id=?",(entity,)).fetchone()[0]
                    prepare_key, claim_key, commit_key = uid(),uid(),uid()
                    prepare = lambda:self.transfers.prepare(actor,prepare_key,entity,source,fences[source],target,version)
                    if index%4==0:
                        self.fault("TransferPrepared",prepare)
                    prepared = prepare()
                    self.assertEqual(prepare(),prepared)
                    if index%4==3:
                        abort_key = uid()
                        abort = lambda:self.transfers.abort(actor,abort_key,prepared["transfer_id"],fences[source])
                        self.fault("TransferAborted",abort)
                        aborted = abort()
                        self.assertEqual(abort(),aborted)
                        with self.assertRaises(Conflict):
                            self.transfers.claim(recipient,uid(),prepared["token"],fences[target])
                        version = self.store.db.execute("SELECT version FROM entity WHERE id=?",(entity,)).fetchone()[0]
                        prepare_key = uid()
                        prepared = prepare()
                    claim = lambda:self.transfers.claim(recipient,claim_key,prepared["token"],fences[target])
                    if index%4==1:
                        self.fault("TransferClaimed",claim)
                    claimed = claim()
                    self.assertEqual(claim(),claimed)
                    # Checkpoint contains living identities and exact ledger,
                    # never a corpse or a newly generated starting inventory.
                    expected = [player] if entity==player else [group,npc,mutant]
                    self.assertEqual(claimed["checkpoint"]["ids"],expected)
                    self.assertNotIn(casualty,claimed["checkpoint"]["ids"])
                    if index%50 in (0,1):
                        self.store.close()
                        self.open()
                        self.assertEqual(claim(),claimed)
                    commit = lambda:self.transfers.commit(recipient,commit_key,prepared["transfer_id"],fences[target])
                    if index%4==2:
                        self.fault("TransferCommitted",commit)
                    committed = commit()
                    self.assertEqual(commit(),committed)
                    locations[entity] = target
                    for entity_id in expected:
                        row = self.store.db.execute("SELECT * FROM entity WHERE id=?",(entity_id,)).fetchone()
                        self.assertEqual((row["location"],row["writer"],row["fence"]),(target,recipient,fences[target]))
                        self.assertEqual(row["state"],initial_states[entity_id])
                    with self.assertRaises(Conflict):
                        self.ownership.update_entity(actor,uid(),entity,fences[source],version,states[entity])
                    self.assertEqual([tuple(r) for r in self.store.db.execute("SELECT * FROM item ORDER BY id")],initial_items)
                    body = self.store.db.execute("SELECT * FROM entity WHERE id=?",(casualty,)).fetchone()
                    self.assertEqual((body["alive"],body["location"],body["state"]),(0,"cordon",initial_states[casualty]))
                    self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],5)
                    self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM player_session WHERE state='ACTIVE'").fetchone()[0],1)
                    self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM transfer WHERE state IN ('PREPARED','CLAIMED')").fetchone()[0],0)
                self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='TransferCommitted'").fetchone()[0],1000)
                self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='TransferAborted'").fetchone()[0],250)
                self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='EntityDied'").fetchone()[0],1)
            finally:
                self.store.close()

    def test_process_crash_on_each_handoff_phase_before_and_after_commit(self):
        code = '''
import json,os,sys
from lostzone import Store,World
from lostzone.transfers import Transfers
s=Store(sys.argv[1])
w=World(s,world_id=123,seed=456,monotonic=lambda:0,wall=lambda:1_800_000_000_000_000_000)
t=Transfers(w,b"stress-key"*4)
phase,timing,args=sys.argv[2],sys.argv[3],json.loads(sys.argv[4])
kind={"prepare":"TransferPrepared","claim":"TransferClaimed","commit":"TransferCommitted","abort":"TransferAborted"}[phase]
original=s.event
def interrupt(tx,aggregate,event_type,*values,**options):
 result=original(tx,aggregate,event_type,*values,**options)
 if timing=="before" and event_type==kind: os._exit(23)
 return result
s.event=interrupt
getattr(t,phase)(*args)
os._exit(24)
'''
        environment = {**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1])}
        for phase in ("prepare","claim","commit","abort"):
            for timing in ("before","after"):
                with self.subTest(phase=phase,timing=timing), tempfile.TemporaryDirectory() as folder:
                    self.path = Path(folder)/"world.db"
                    self.open()
                    try:
                        a = self.world.claim_location("a",uid(),"cordon")["fence"]
                        b = self.world.claim_location("b",uid(),"garbage")["fence"]
                        npc,item,key = uid(),uid(),uid()
                        self.ownership.create_entity("a",uid(),npc,"NPC","cordon",a,{"health":.72,"name":"Сталкер"})
                        self.ownership.create_item("a",uid(),item,"medkit","cordon",a,"NPC",npc,quantity=3,state={"condition":.83})
                        prepared = None
                        if phase != "prepare":
                            prepared = self.transfers.prepare("a",uid(),npc,"cordon",a,"garbage",1)
                        if phase == "commit":
                            self.transfers.claim("b",uid(),prepared["token"],b)
                        args = {"prepare":["a",key,npc,"cordon",a,"garbage",1],
                                "claim":["b",key,prepared["token"] if prepared else "",b],
                                "commit":["b",key,prepared["transfer_id"] if prepared else "",b],
                                "abort":["a",key,prepared["transfer_id"] if prepared else "",a]}[phase]
                        actor = args[0]
                        before = self.fingerprint()
                        self.store.close()
                        child = subprocess.run([sys.executable,"-c",code,str(self.path),phase,timing,json.dumps(args)],
                                               env=environment,capture_output=True,timeout=20)
                        self.assertEqual(child.returncode,23 if timing=="before" else 24,child.stderr)
                        self.open()
                        saved = self.store.db.execute("SELECT result FROM command_result WHERE actor=? AND id=?",(actor,key)).fetchone()
                        self.assertEqual(saved is not None,timing=="after")
                        if timing=="before":
                            restored = self.fingerprint()
                            # Boot increments epoch/revision; semantic rows,
                            # journal, commands and pending transfer stay exact.
                            self.assertEqual(restored[:4],before[:4])
                            self.assertEqual(restored[5:],before[5:])
                        result = getattr(self.transfers,phase)(*args)
                        if saved is not None:
                            self.assertEqual(result,json.loads(saved[0]))
                        self.assertEqual(getattr(self.transfers,phase)(*args),result)
                        if phase=="prepare":
                            prepared=result
                        if phase in ("prepare","claim"):
                            self.transfers.claim("b",uid(),prepared["token"],b)
                            self.transfers.commit("b",uid(),prepared["transfer_id"],b)
                        row = self.store.db.execute("SELECT location,writer FROM entity WHERE id=?",(npc,)).fetchone()
                        self.assertEqual(tuple(row),("cordon","a") if phase=="abort" else ("garbage","b"))
                        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],1)
                        ledger = self.store.db.execute("SELECT holder,quantity,state FROM item WHERE id=?",(item,)).fetchone()
                        self.assertEqual(tuple(ledger),(npc,3,'{"condition":0.83}'))
                        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0],1)
                        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM transfer WHERE state IN ('PREPARED','CLAIMED')").fetchone()[0],0)
                    finally:
                        self.store.close()


if __name__ == "__main__":
    unittest.main()
