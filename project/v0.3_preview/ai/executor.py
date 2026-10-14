"""Executed exclusively on Controller's actor thread; never touches a network."""
from collections import OrderedDict
from copy import deepcopy
import json

from .tools import CANCELLABLE, WRITES, normalize, query, task_view


class BusinessExecutor:
    def __init__(self, controller):
        self.controller = controller
        self.ledger = OrderedDict()

    def validate(self, actions):
        sim = self.controller.sim
        projected = {k: [t.priority, t.status] for k, t in sim.tasks.items()}
        for action in actions:
            if action["operation"] == "add":
                if action["pickup"] > len(sim.warehouse.pickups) or action["delivery"] > len(sim.warehouse.deliveries):
                    raise ValueError("当前场景没有此取货点或配送点")
                continue
            task_id = action["task_id"]
            if task_id not in projected:
                raise ValueError(f"T{task_id:03}不存在")
            level, phase = projected[task_id]
            if action["operation"] == "cancel":
                if phase not in CANCELLABLE:
                    raise ValueError(f"T{task_id:03}已开始装货或已经结束，不能取消")
                projected[task_id][1] = "cancelled"
            else:
                if phase in ("completed", "cancelled"):
                    raise ValueError(f"T{task_id:03}已经结束，不能升级")
                target = min(5, level + 1) if action["mode"] == "increment" else action["priority"]
                if target < level:
                    raise ValueError(f"T{task_id:03}不支持降低等级")
                projected[task_id][0] = target

    def run(self, envelope):
        c = self.controller
        name, raw = envelope["name"], envelope["arguments"]
        key = envelope["operation_id"]
        fingerprint = json.dumps([name, raw], sort_keys=True, ensure_ascii=False)
        if key in self.ledger:
            old = self.ledger[key]
            if old["fingerprint"] != fingerprint:
                raise ValueError("同一操作标识不能使用不同参数")
            return deepcopy(old["result"])
        valid = envelope.get("valid", lambda: True)
        def fresh():
            return envelope["generation"] == c.generation and valid()
        if not fresh():
            return {"status": "finished", "actions": [], "error": "请求已停止或工作场景已更新，未执行"}
        args = normalize(name, raw)
        if name not in WRITES:
            return query(c.sim, name, args)
        result = {"status": "running", "actions": []}
        self.ledger[key] = {"fingerprint": fingerprint, "result": result}
        try:
            self.validate(args)
        except ValueError as exc:
            result.update(status="finished", error=str(exc), actions=[{"operation": a["operation"], "outcome": "not_executed", "reason": "整批预检未通过"} for a in args])
            return deepcopy(result)
        stop_reason = None
        for action in args:
            if stop_reason or not fresh():
                result["actions"].append({"operation": action["operation"], "outcome": "not_executed", "reason": stop_reason or "请求已停止或工作场景已更新"})
                continue
            try:
                self.validate([action])
            except ValueError as exc:
                stop_reason = str(exc)
                result["actions"].append({"operation": action["operation"], "outcome": "rejected", "reason": stop_reason})
                continue
            op = action["operation"]
            task_id = c.sim.next_id if op == "add" else action["task_id"]
            target = None
            if op == "priority":
                current = c.sim.tasks[task_id].priority
                target = min(5, current + 1) if action["mode"] == "increment" else action["priority"]
                if current == target:
                    result["actions"].append({"operation": op, "outcome": "no_change", **task_view(c.sim.tasks[task_id], c.sim.warehouse), "reason": "任务已经达到此等级"})
                    continue
            item = {"operation": op, "outcome": "not_executed", "task_id": f"T{task_id:03}"}
            result["actions"].append(item)
            try:
                if op == "add":
                    c.sim.command("add", pickup=c.sim.warehouse.pickups[action["pickup"]-1], delivery=c.sim.warehouse.deliveries[action["delivery"]-1], priority=action["priority"])
                elif op == "priority":
                    c.sim.command("priority", task_id=task_id, priority=target)
                else:
                    c.sim.command("cancel", task_id=task_id)
                task = c.sim.tasks.get(task_id)
                applied = task is not None and (op == "add" or (op == "cancel" and task.status == "cancelled") or (op == "priority" and task.priority == target))
                item.update(outcome="applied" if applied else "rejected")
                if task:
                    item.update(task_view(task, c.sim.warehouse))
                if not applied:
                    stop_reason = "业务条件已改变，操作未生效"
                    item["reason"] = stop_reason
                    continue
                # Record committed domain outcome BEFORE planning can fail.
                c._publish()
                c._plan()
                c.sim.assert_invariants()
                item.update(task_view(c.sim.tasks[task_id], c.sim.warehouse))
                item["planning"] = "unavailable" if c.sim.dirty else "available"
                if c.sim.dirty:
                    stop_reason = "任务操作已生效，当前预算内尚未形成可执行路线"
                    item["reason"] = stop_reason
            except Exception:
                task = c.sim.tasks.get(task_id)
                if task and (op == "add" or (op == "cancel" and task.status == "cancelled") or (op == "priority" and task.priority == target)):
                    item.update(outcome="applied", **task_view(task, c.sim.warehouse))
                stop_reason = "业务处理或路线生成异常，请查看已生效结果；未继续执行"
                item.update(planning="unavailable", reason=stop_reason)
                c.sim.paused = True
                c._publish()
        result["status"] = "finished"
        while len(self.ledger) > 2048:
            self.ledger.popitem(last=False)
        return deepcopy(result)
