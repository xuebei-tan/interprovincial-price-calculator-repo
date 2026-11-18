from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd


class PowerTradeCalculator:
    """Calculate delivered inter-provincial electricity prices from an Excel parameter workbook."""

    SHEET_PROVINCE = "A省级电网参数及外送特例"
    SHEET_PROJECT = "B跨省跨区专项工程参数及拓扑"
    SHEET_REGION = "C区域电网输电参数"

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"Parameter workbook not found: {self.filepath}")

        self.df_a = pd.read_excel(self.filepath, sheet_name=self.SHEET_PROVINCE)
        self.df_b = pd.read_excel(self.filepath, sheet_name=self.SHEET_PROJECT)
        self.df_c = pd.read_excel(self.filepath, sheet_name=self.SHEET_REGION)

        self._validate_columns()
        self.prov_data: dict[str, dict[str, float]] = {}
        self.region_data: dict[str, dict[str, float]] = {}
        self.prov_region: dict[str, str] = {}
        self.prov_region_group: dict[str, str] = {}
        self.region_group: dict[str, str] = {}

        self._load_provinces()
        self._load_regions()
        self.G = nx.DiGraph()
        self._build_graph()

    @property
    def provinces(self) -> list[str]:
        return sorted(self.prov_data.keys())

    @staticmethod
    def _safe_float(value: Any) -> float:
        if pd.isna(value) or str(value).strip() in {"", "暂缺"}:
            return 0.0
        return float(value)

    def _validate_columns(self) -> None:
        required = {
            self.SHEET_PROVINCE: {
                "省份",
                "受端电量电价(元/MWh)",
                "受端省内线损率(%)",
                "外送特例电量电价(元/MWh)",
                "外送特例线损率(%)",
            },
            self.SHEET_PROJECT: {
                "通道名称",
                "起点省份",
                "终点省份",
                "电量电价(元/MWh)",
                "线损率(%)",
            },
            self.SHEET_REGION: {
                "区域",
                "同价板块",
                "区域电量电价(元/MWh)",
                "区域线损率(%)",
                "包含省份",
            },
        }
        frames = {
            self.SHEET_PROVINCE: self.df_a,
            self.SHEET_PROJECT: self.df_b,
            self.SHEET_REGION: self.df_c,
        }
        errors = []
        for sheet, columns in required.items():
            missing = columns - set(frames[sheet].columns)
            if missing:
                errors.append(f"{sheet}: missing {', '.join(sorted(missing))}")
        if errors:
            raise ValueError("Workbook structure is invalid. " + " | ".join(errors))

    def _load_provinces(self) -> None:
        for _, row in self.df_a.iterrows():
            province = str(row["省份"]).strip()
            if not province or province == "nan":
                continue
            self.prov_data[province] = {
                "recv_price": self._safe_float(row["受端电量电价(元/MWh)"]),
                "recv_loss": self._safe_float(row["受端省内线损率(%)"]),
                "send_price": self._safe_float(row["外送特例电量电价(元/MWh)"]),
                "send_loss": self._safe_float(row["外送特例线损率(%)"]),
            }

    def _load_regions(self) -> None:
        for _, row in self.df_c.iterrows():
            region = str(row["区域"]).strip()
            group = str(row["同价板块"]).strip()
            self.region_data[region] = {
                "price": float(row["区域电量电价(元/MWh)"]),
                "loss": float(row["区域线损率(%)"]),
            }
            self.region_group[region] = group
            provinces = (
                str(row["包含省份"])
                .replace(" ", "")
                .replace("\u3000", "")
                .replace("\xa0", "")
                .split(",")
            )
            for province in provinces:
                if province:
                    self.prov_region[province] = region
                    self.prov_region_group[province] = group

    def _normalize_province(self, name: Any) -> str:
        value = str(name).strip().replace(" ", "").replace("\u3000", "").replace("\xa0", "")
        for province in self.prov_region:
            if province in value or value in province:
                return province
        return value

    def _build_graph(self) -> None:
        for province, region in self.prov_region.items():
            self.G.add_node(province, type="province")
            region_node = f"R_{region}"
            self.G.add_node(region_node, type="region", group=self.region_group[region])
            self.G.add_edge(province, region_node, price=0, loss=0, is_direct=False)
            self.G.add_edge(region_node, province, price=0, loss=0, is_direct=False)

        for _, row in self.df_b.iterrows():
            if str(row.get("是否启用", "是")).strip() != "是":
                continue
            name = str(row["通道名称"]).strip()
            start_prov = self._normalize_province(row["起点省份"])
            end_prov = self._normalize_province(row["终点省份"])
            price = float(row["电量电价(元/MWh)"])
            loss = min(max(float(row["线损率(%)"]), 0.0), 0.99)
            if end_prov == "华中各省":
                continue
            start_region = self.prov_region.get(start_prov)
            end_region = self.prov_region.get(end_prov)
            if not start_region or not end_region:
                continue

            project_node = f"P_{name}"
            self.G.add_node(project_node, type="project", price=price, loss=loss, name=name,
                            start_prov=start_prov, start_region=start_region, end_prov=end_prov)
            self.G.add_edge(f"R_{start_region}", project_node, price=0, loss=0, is_direct=False)
            self.G.add_edge(project_node, f"R_{end_region}", price=0, loss=0, is_direct=False)

            reverse_node = f"P_{name}(反向)"
            self.G.add_node(reverse_node, type="project", price=price, loss=loss,
                            name=f"{name}(反向)", start_prov=None, start_region=None, end_prov=start_prov)
            self.G.add_edge(f"R_{end_region}", reverse_node, price=0, loss=0, is_direct=False)
            self.G.add_edge(reverse_node, f"R_{start_region}", price=0, loss=0, is_direct=False)

    def calculate_path(self, path: list[str], start_energy_price: float, green_premium: float):
        current_price = start_energy_price
        start_prov, end_prov = path[0], path[-1]
        details = []

        start_info = self.prov_data[start_prov]
        base = current_price
        loss_amount = round(base * start_info["send_loss"] / (1 - start_info["send_loss"]), 3)
        current_price = round(base + loss_amount + start_info["send_price"], 3)
        details.append({"环节": f"{start_prov} · 送出省送出侧", "输电价": start_info["send_price"],
                        "网损率": start_info["send_loss"], "基准价": base,
                        "网损折价": loss_amount, "结算价": current_price})

        used_groups, fee_after_project = set(), set()
        last_project_end_prov = next(
            (self.G.nodes[node].get("end_prov") for node in reversed(path)
             if self.G.nodes[node].get("type") == "project"), None
        )
        is_direct_landing = False
        for node in reversed(path[:-1]):
            node_type = self.G.nodes[node].get("type")
            if node_type == "project":
                is_direct_landing = True
                break
            if node_type == "province":
                break

        end_region_name = self.prov_region.get(end_prov)
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            node_u, node_v = self.G.nodes[u], self.G.nodes[v]
            if node_u.get("type") == "project":
                base = current_price
                loss_amount = round(base * node_u["loss"] / (1 - node_u["loss"]), 3)
                current_price = round(base + loss_amount + node_u["price"], 3)
                details.append({"环节": f"{node_u['name']} · 工程送受端关口", "输电价": node_u["price"],
                                "网损率": node_u["loss"], "基准价": base,
                                "网损折价": loss_amount, "结算价": current_price})
                continue

            region_name = None
            if node_u.get("type") == "region":
                region_name = u.removeprefix("R_")
            elif node_v.get("type") == "region":
                region_name = v.removeprefix("R_")
            if not region_name:
                continue

            group = self.region_group.get(region_name, region_name)
            if group in used_groups:
                continue

            skip = region_name == self.prov_region.get(start_prov) and any(
                self.G.nodes[node].get("type") == "project"
                and self.G.nodes[node].get("start_prov") == start_prov
                for node in path
            )
            if skip:
                used_groups.add(group)
                continue

            if (is_direct_landing and region_name == end_region_name
                    and last_project_end_prov == end_prov and fee_after_project):
                used_groups.add(group)
                continue

            used_groups.add(group)
            region_info = self.region_data.get(region_name)
            if region_info:
                base = current_price
                loss_amount = round(base * region_info["loss"] / (1 - region_info["loss"]), 3)
                current_price = round(base + loss_amount + region_info["price"], 3)
                details.append({"环节": f"{region_name} · 区域电网关口", "输电价": region_info["price"],
                                "网损率": region_info["loss"], "基准价": base,
                                "网损折价": loss_amount, "结算价": current_price})
                if i > 0 and self.G.nodes[path[i - 1]].get("type") == "project":
                    fee_after_project.add(group)

        end_info = self.prov_data[end_prov]
        base = current_price
        if is_direct_landing:
            details.append({"环节": f"{end_prov} · 落地省落地侧", "输电价": 0.0, "网损率": 0.0,
                            "基准价": base, "网损折价": 0.0, "结算价": current_price})
        else:
            loss_amount = round(base * end_info["recv_loss"] / (1 - end_info["recv_loss"]), 3)
            current_price = round(base + loss_amount + end_info["recv_price"], 3)
            details.append({"环节": f"{end_prov} · 落地省落地侧", "输电价": end_info["recv_price"],
                            "网损率": end_info["recv_loss"], "基准价": base,
                            "网损折价": loss_amount, "结算价": current_price})

        final_price = round(current_price + green_premium, 3)
        details.append({"环节": f"{end_prov} · 环境价值（穿透不计损）", "输电价": 0.0, "网损率": 0.0,
                        "基准价": current_price, "网损折价": 0.0, "结算价": final_price})
        return final_price, details

    def search_all(self, start_prov: str, end_prov: str, start_energy_price: float,
                   green_premium: float, cutoff: int = 8):
        if start_prov not in self.G or end_prov not in self.G:
            return []
        try:
            raw_paths = nx.all_simple_paths(self.G, source=start_prov, target=end_prov, cutoff=cutoff)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        results, seen_project_sets = [], set()
        for path in raw_paths:
            project_set = tuple(sorted(
                self.G.nodes[node]["name"] for node in path
                if self.G.nodes[node].get("type") == "project"
            ))
            if project_set in seen_project_sets:
                continue
            seen_project_sets.add(project_set)
            final_price, details = self.calculate_path(path, start_energy_price, green_premium)
            path_text = path[0]
            for node in path[:-1]:
                node_data = self.G.nodes[node]
                if node_data.get("type") == "project":
                    path_text += f" → {node_data['name']}"
            path_text += f" → {path[-1]}"
            results.append({"price": final_price, "path_str": path_text, "details": details})

        return sorted(results, key=lambda item: item["price"])
