"""app/synth/catalog.py – Synthetic building supply catalog (40 SKUs).

Each SKU has:
    sku_id, name, category, unit, price, lead_time_days,
    base_weekly_demand, aliases (3-5 written variants)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CatalogItem:
    sku_id: str
    name: str
    category: str
    unit: str
    price: int          # Rupiah
    lead_time_days: int
    base_weekly_demand: float
    initial_stock: float
    aliases: list[str]  # includes the canonical name itself


CATALOG: list[CatalogItem] = [
    # ---- Cement ----
    CatalogItem("SMN001", "Semen Tiga Roda 50kg", "Semen", "sak", 68000, 3, 12.0, 80,
                ["SMN 3R", "semen 3 roda", "semen tiga roda", "semen 3roda 50kg", "Semen Tiga Roda 50kg"]),
    CatalogItem("SMN002", "Semen Gresik 50kg", "Semen", "sak", 70000, 3, 8.0, 50,
                ["semen gresik", "SMN GRK", "gresik 50kg", "Semen Gresik 50kg", "s gresik"]),
    CatalogItem("SMN003", "Semen Holcim 40kg", "Semen", "sak", 60000, 3, 5.0, 30,
                ["holcim 40", "semen holcim", "SMN HLC", "Semen Holcim 40kg", "holcim"]),

    # ---- Paint ----
    CatalogItem("CAT001", "Cat Tembok Putih 5kg", "Cat", "kg", 45000, 2, 6.0, 40,
                ["cat tembok 5kg", "cat putih 5kg", "CAT TMB", "Cat Tembok Putih 5kg", "cat tmbok putih"]),
    CatalogItem("CAT002", "Cat Besi Merah 1kg", "Cat", "kg", 55000, 2, 3.0, 20,
                ["cat besi merah", "cat besi 1kg", "CAT BSI", "Cat Besi Merah 1kg", "c besi merah"]),
    CatalogItem("CAT003", "Cat Kayu Coklat 1kg", "Cat", "kg", 48000, 2, 2.5, 15,
                ["cat kayu coklat", "cat kayu 1kg", "CAT KYU", "Cat Kayu Coklat 1kg", "c kayu cklat"]),

    # ---- Nails & Screws ----
    CatalogItem("PKU001", "Paku Biasa 2 inch", "Paku & Sekrup", "kg", 18000, 1, 4.0, 25,
                ["paku 2 inch", "paku biasa 2\"", "PKU 2IN", "Paku Biasa 2 inch", "paku 2in"]),
    CatalogItem("PKU002", "Paku Biasa 3 inch", "Paku & Sekrup", "kg", 17000, 1, 3.5, 20,
                ["paku 3 inch", "paku biasa 3\"", "PKU 3IN", "Paku Biasa 3 inch", "paku 3in"]),
    CatalogItem("SKR001", "Sekrup Kayu 3cm", "Paku & Sekrup", "lusin", 8000, 1, 5.0, 30,
                ["sekrup kayu 3", "skrup kayu 3cm", "SKR KYU", "Sekrup Kayu 3cm", "skrup 3cm"]),
    CatalogItem("SKR002", "Sekrup Dinding Fischer", "Paku & Sekrup", "pcs", 2500, 1, 8.0, 50,
                ["sekrup fischer", "fisher screw", "SKR FSC", "Sekrup Dinding Fischer", "skrup fischer"]),

    # ---- Pipes & Fittings ----
    CatalogItem("PVC001", "Pipa PVC 3/4 inch", "Pipa & Fitting", "btg", 35000, 3, 7.0, 45,
                ["pipa pvc 3/4", "pipa 3/4", "PVC 3/4", "Pipa PVC 3/4 inch", "pipa pvc 3 4"]),
    CatalogItem("PVC002", "Pipa PVC 1 inch", "Pipa & Fitting", "btg", 42000, 3, 4.5, 30,
                ["pipa pvc 1 inch", "pipa 1in", "PVC 1IN", "Pipa PVC 1 inch", "pipa pvc 1\""]),
    CatalogItem("FTG001", "Elbow PVC 3/4 inch", "Pipa & Fitting", "pcs", 5000, 2, 10.0, 60,
                ["elbow 3/4", "elbow pvc", "ELB 3/4", "Elbow PVC 3/4 inch", "elbow 3 4"]),
    CatalogItem("FTG002", "Tee PVC 3/4 inch", "Pipa & Fitting", "pcs", 5500, 2, 8.0, 50,
                ["tee 3/4", "tee pvc 3/4", "TEE PVC", "Tee PVC 3/4 inch", "tee 3 4"]),

    # ---- Cables & Electrical ----
    CatalogItem("KBL001", "Kabel NYM 2x1.5mm", "Kabel & Listrik", "m", 12000, 2, 15.0, 100,
                ["kabel nym 2x1.5", "kabel listrik 1.5", "KBL NYM", "Kabel NYM 2x1.5mm", "kbl nym 1.5"]),
    CatalogItem("KBL002", "Kabel NYM 3x2.5mm", "Kabel & Listrik", "m", 18000, 2, 10.0, 70,
                ["kabel nym 3x2.5", "kabel 3x2.5", "KBL NYM25", "Kabel NYM 3x2.5mm", "kbl nym 2.5"]),
    CatalogItem("SWC001", "Saklar Tunggal", "Kabel & Listrik", "pcs", 15000, 1, 5.0, 30,
                ["saklar tunggal", "saklar 1", "SWC TGL", "Saklar Tunggal", "switch tunggal"]),
    CatalogItem("STP001", "Stop Kontak Tanam", "Kabel & Listrik", "pcs", 22000, 1, 6.0, 40,
                ["stop kontak", "colokan tanam", "STP KNK", "Stop Kontak Tanam", "stopkontak"]),

    # ---- Tiles ----
    CatalogItem("KRM001", "Keramik 40x40 Putih", "Keramik", "m2", 85000, 5, 5.0, 35,
                ["keramik 40x40", "keramik putih", "KRM 40", "Keramik 40x40 Putih", "krm 40x40"]),
    CatalogItem("KRM002", "Keramik 30x30 Abu-abu", "Keramik", "m2", 70000, 5, 3.5, 25,
                ["keramik 30x30", "keramik abu", "KRM 30", "Keramik 30x30 Abu-abu", "krm 30x30"]),
    CatalogItem("KRM003", "Granit 60x60 Putih", "Keramik", "m2", 150000, 5, 2.0, 15,
                ["granit 60x60", "granit putih", "GRN 60", "Granit 60x60 Putih", "grnt 60x60"]),

    # ---- Tools ----
    CatalogItem("ALT001", "Kuas Cat 3 inch", "Alat", "pcs", 12000, 1, 3.0, 20,
                ["kuas 3 inch", "kuas cat 3", "KUS 3IN", "Kuas Cat 3 inch", "kuas 3in"]),
    CatalogItem("ALT002", "Rol Cat 9 inch", "Alat", "pcs", 25000, 1, 2.5, 15,
                ["rol cat 9 inch", "roller 9in", "ROL 9IN", "Rol Cat 9 inch", "roll 9 inch"]),
    CatalogItem("ALT003", "Meteran 5m", "Alat", "pcs", 35000, 1, 2.0, 12,
                ["meteran 5m", "roll meter 5", "MTR 5M", "Meteran 5m", "meter 5 m"]),
    CatalogItem("ALT004", "Gergaji Kayu", "Alat", "pcs", 65000, 2, 1.0, 8,
                ["gergaji kayu", "saw kayu", "GRG KYU", "Gergaji Kayu", "gergaji"]),

    # ---- Timber ----
    CatalogItem("KYU001", "Kayu Balok 5x10x400", "Kayu", "btg", 45000, 4, 6.0, 40,
                ["balok 5x10", "kayu balok", "KYU BLK", "Kayu Balok 5x10x400", "balok kayu"]),
    CatalogItem("KYU002", "Triplek 9mm 4x8", "Kayu", "lbr", 120000, 4, 4.0, 25,
                ["triplek 9mm", "plywood 9mm", "TRP 9MM", "Triplek 9mm 4x8", "triplek 9"]),
    CatalogItem("KYU003", "Kayu Reng 3x5x400", "Kayu", "btg", 18000, 4, 8.0, 55,
                ["reng 3x5", "kayu reng", "KYU RNG", "Kayu Reng 3x5x400", "reng 3 5"]),

    # ---- Sand & Stone ----
    CatalogItem("PSR001", "Pasir Beton 1 Kubik", "Pasir & Batu", "m3", 350000, 2, 3.0, 20,
                ["pasir beton", "pasir 1m3", "PSR BTN", "Pasir Beton 1 Kubik", "pasir beton 1 m3"]),
    CatalogItem("PSR002", "Pasir Pasang 1 Kubik", "Pasir & Batu", "m3", 280000, 2, 2.5, 15,
                ["pasir pasang", "pasir halus", "PSR PSG", "Pasir Pasang 1 Kubik", "pasir pasang 1m3"]),
    CatalogItem("BTU001", "Batu Split 1-2 1 Kubik", "Pasir & Batu", "m3", 300000, 2, 2.0, 12,
                ["batu split 1-2", "split 1/2", "BTU SPL", "Batu Split 1-2 1 Kubik", "batu split"]),
    CatalogItem("BTU002", "Bata Merah 1000pcs", "Pasir & Batu", "lot", 850000, 3, 1.5, 10,
                ["bata merah", "batu bata", "BTU MRH", "Bata Merah 1000pcs", "bata 1000"]),

    # ---- Misc ----
    CatalogItem("SKM001", "Sika Plafon 5kg", "Semen & Plester", "kg", 38000, 2, 4.0, 25,
                ["sika plafon", "plafon sika", "SKM PLF", "Sika Plafon 5kg", "sika 5kg"]),
    CatalogItem("SKM002", "Mortar Lantai 40kg", "Semen & Plester", "sak", 75000, 3, 3.5, 22,
                ["mortar lantai", "mortar 40kg", "MRT LNT", "Mortar Lantai 40kg", "mortar 40"]),
    CatalogItem("WRC001", "Waterproofing 4kg", "Waterproofing", "kg", 95000, 2, 2.5, 15,
                ["waterproofing 4kg", "WC 4kg", "WRC 4KG", "Waterproofing 4kg", "waterproof 4kg"]),
    CatalogItem("GRC001", "GRC Board 60x120", "Panel", "lbr", 65000, 3, 3.0, 20,
                ["grc board", "grc 60x120", "GRC BRD", "GRC Board 60x120", "papan grc"]),
    CatalogItem("ISO001", "Isotank 500L", "Tangki Air", "pcs", 750000, 7, 0.5, 4,
                ["isotank 500l", "tangki 500", "ISO 500", "Isotank 500L", "tank air 500"]),
    CatalogItem("KNS001", "Konektor Sambungan Pipa", "Pipa & Fitting", "pcs", 8500, 1, 6.0, 40,
                ["konektor pipa", "sambungan pipa", "KNS PPA", "Konektor Sambungan Pipa", "konektor"]),
]
