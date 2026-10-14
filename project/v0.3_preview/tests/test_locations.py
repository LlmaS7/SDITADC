"""Business mapping, geometry integrity, replay and model/tool orchestration.

Scripted providers verify protocol and state changes, not real LLM comprehension.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.configuration import Configuration
from ai.service import AIService
from ai.tools import normalize, query
from controller import Controller
from locations import build_locations
from map_format import validate_map
from persistence import load, save
from simulation import Simulation
from warehouse import Warehouse
from test_ai import MemoryCredentials
from test_maps import small_map


def named_map():
    value = small_map()
    value["locations"] = {
        "deliveries": [{"id": "D1", "name": "包装区", "aliases": ["包装工位"]}],
        "shelves": [{"id": "S04", "name": "4号货架", "aliases": ["补货架"],
                     "pickup_id": "P02", "cells": [[5,4], [6,4], [7,4], [5,5]]}]}
    return value


class LocationTests(unittest.TestCase):
    def test_builtin_registration_and_no_guesses_for_ambiguous_or_old_maps(self):
        standard = Warehouse(1)
        large = Warehouse(1, "warehouse_64x48")
        self.assertEqual(len(standard.locations["shelves"]), 20)
        self.assertEqual(len(large.locations["shelves"]), 64)
        self.assertEqual(standard.locations["shelves"][3]["pickup_id"], "P04")
        self.assertEqual(large.locations["shelves"][-1]["pickup_id"], "P64")
        self.assertEqual(Warehouse(1, "movingai_warehouse").locations["shelves"], [])
        legacy = build_locations(small_map())
        self.assertEqual(legacy["shelves"], [])
        self.assertEqual([p["id"] for p in legacy["pickups"]], ["P01", "P02"])

    def test_nonmatching_shelf_number_and_detached_alias_catalog(self):
        sim = Simulation(1, initial_tasks=0, map_definition=named_map())
        result = query(sim, "get_locations", normalize("get_locations", {}))
        self.assertEqual(result["shelf"][0]["id"], "S04")
        self.assertEqual(result["shelf"][0]["pickup_id"], "P02")
        self.assertEqual(result["delivery"][0]["name"], "包装区")
        self.assertNotIn("cells", result["shelf"][0])
        result["shelf"][0]["aliases"].append("外部修改")
        self.assertNotIn("外部修改", sim.warehouse.locations["shelves"][0]["aliases"])
        self.assertEqual(set(query(sim, "get_locations", {"kind": "shelf"})), {"shelf", "note"})

    def test_unknown_overlapping_disconnected_and_invalid_service_mapping_rejected(self):
        cases = []
        value=named_map();value["locations"]["shelves"][0]["pickup_id"]="P04";cases.append(value)
        value=named_map();value["locations"]["shelves"][0]["cells"]=[[4,4]];cases.append(value)
        value=named_map();value["locations"]["shelves"][0]["cells"]=[[5,4]];cases.append(value)
        value=named_map();value["locations"]["shelves"][0]["cells"]=[[5,5],[7,4]];cases.append(value)
        value=named_map();value["locations"]["shelves"].append(deepcopy(value["locations"]["shelves"][0]));cases.append(value)
        value=named_map();value["locations"]["shelves"].append({**deepcopy(value["locations"]["shelves"][0]), "id":"S05"});cases.append(value)
        value=named_map();value["locations"]["deliveries"][0]["id"]="D99";cases.append(value)
        value=named_map();value["locations"]["shelves"][0]["aliases"]=["重复", "重复"];cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_map(value)

    def test_shared_alias_keeps_all_candidates_instead_of_resolving_locally(self):
        value = named_map()
        value["points"]["deliveries"].append([8,7])
        value["locations"]["deliveries"] = [{"id":"D1", "name":"包装工位A", "aliases":["包装区"]}, {"id":"D2", "name":"包装工位B", "aliases":["包装区"]}]
        sim=Simulation(1, initial_tasks=0, map_definition=value)
        result=query(sim,"get_locations",{"kind":"all"})
        self.assertEqual([d["id"] for d in result["delivery"] if "包装区" in d["aliases"]], ["D1", "D2"])

    def test_map_snapshot_replay_keeps_names_and_original_pickup_mapping(self):
        with TemporaryDirectory() as tmp:
            sim=Simulation(1,initial_tasks=0,map_id="missing_named_map",map_definition=named_map())
            sim.command("add",pickup=(7,3),delivery=(7,7),priority=2)
            with patch("persistence.OUTPUTS",Path(tmp)):
                replay=load(save(sim))
            self.assertEqual(replay.warehouse.locations, sim.warehouse.locations)
            self.assertEqual(replay.tasks[1].pickup, (7,3))


class ScriptedLocationModel:
    """A protocol fixture consumes actual tool data; it is not a language parser."""
    def __init__(self, clarify=False, ambiguous=False):
        self.calls=[]
        self.catalog=None
        self.clarify=clarify
        self.ambiguous=ambiguous

    def chat(self, config, messages, tools, token, on_text=None):
        self.calls.append(deepcopy(messages))
        last=messages[-1]
        def call(name, args):
            return {"role":"assistant", "content":"", "reasoning_content":"protocol fixture", "tool_calls":[{"id":f"fixture-{len(self.calls)}", "type":"function", "function":{"name":name,"arguments":json.dumps(args)}}]},None
        if last["role"]=="user":
            if self.catalog and self.clarify:
                return call("create_tasks", {"tasks":[{"pickup_id":self.catalog["shelf"][0]["pickup_id"], "delivery_id":self.catalog["delivery"][0]["id"]}]})
            return call("get_locations", {})
        result=json.loads(last["content"])
        if "shelf" in result:
            self.catalog=result
            if self.clarify or self.ambiguous:
                content="请问送到哪里？" if self.clarify else "包装区对应多个配送点，请明确选择。"
                if on_text:on_text(content)
                return {"role":"assistant","content":content,"reasoning_content":"protocol fixture"},None
            return call("create_tasks", {"tasks":[{"pickup_id":result["shelf"][0]["pickup_id"],"delivery_id":result["delivery"][0]["id"],"priority":5}]})
        content="任务已创建，取送位置以业务结果卡为准。"
        if on_text:on_text(content)
        return {"role":"assistant","content":content,"reasoning_content":"protocol fixture"},None


class LocationWorkflowTests(unittest.TestCase):
    def workflow(self, provider, messages, definition=None):
        with TemporaryDirectory() as tmp, patch("warehouse.load_map",return_value=validate_map(definition or named_map())):
            c=Controller(paused=True);c.start();c.submit("pause",{"paused":True}).result(10)
            cfg=Configuration(Path(tmp)/"settings.json",MemoryCredentials())
            cfg.save({"api_key":"SCRIPTED_TEST_KEY", "model":"scripted-protocol-model"})
            service=AIService(c,cfg,provider)
            try:
                for index, message in enumerate(messages):
                    service.launch("message",{"text":message,"generation":c.generation,"task_id":None})
                    deadline=monotonic()+10
                    while service.public()["busy"] and monotonic()<deadline:sleep(.02)
                    self.assertFalse(service.public()["busy"])
                    if provider.clarify and index==0:self.assertEqual(len(c.sim.tasks),9)
                self.assertEqual([e for e in service.events if e["kind"]=="error"],[])
                return deepcopy(c.sim.tasks), deepcopy(list(service.events)), c.state()["paused"]
            finally:
                service.close();c.stop(save_on_exit=False)

    def test_shelf_to_destination_uses_catalog_not_matching_numbers(self):
        provider=ScriptedLocationModel()
        tasks,events,paused=self.workflow(provider,["将四号货架的货物送到包装区，设为紧急"])
        self.assertEqual(tasks[10].pickup,(7,3))
        self.assertEqual(tasks[10].delivery,(7,7))
        self.assertEqual(tasks[10].priority,5)
        self.assertTrue(paused)
        item=next(e for e in events if e["kind"]=="result")["result"]["actions"][0]
        self.assertEqual(item["pickup_label"],"4号货架")
        self.assertEqual(item["delivery_name"],"包装区")
        self.assertEqual(item["pickup_id"],"P02")

    def test_followup_completes_request_once_with_first_turn_context(self):
        provider=ScriptedLocationModel(clarify=True)
        tasks,events,_=self.workflow(provider,["将四号货架的货物送走", "送到包装区"])
        self.assertEqual(len(tasks),10)
        self.assertEqual(tasks[10].priority,2)
        second=[messages for messages in provider.calls if messages[-1]["role"]=="user"][-1]
        self.assertTrue(any("将四号货架" in m.get("content","") for m in second))
        self.assertEqual(len([e for e in events if e["kind"]=="result"]),1)

    def test_ambiguous_alias_can_be_clarified_without_creating(self):
        value=named_map();value["points"]["deliveries"].append([8,7])
        value["locations"]["deliveries"]=[{"id":"D1","name":"工位A","aliases":["包装区"]},{"id":"D2","name":"工位B","aliases":["包装区"]}]
        tasks,events,_=self.workflow(ScriptedLocationModel(ambiguous=True),["四号货架送到包装区"],value)
        self.assertEqual(len(tasks),9)
        self.assertEqual([e for e in events if e["kind"]=="result"],[])


if __name__ == "__main__":
    unittest.main()
