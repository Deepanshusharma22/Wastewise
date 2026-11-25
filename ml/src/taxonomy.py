"""WasteWise label taxonomy — the single source of truth for class labels.

Two label levels are used:

* **category** (7 classes) — the primary prediction shown to users.
* **item** (fine-grained, optional) — a specific object type. Only images whose
  source folder identifies a specific object get an item label; generic folders
  (e.g. TrashNet "plastic") get ``None`` and are ignored by the item loss.

The category identifiers below are used verbatim by the backend API, the
Supabase ``predictions.predicted_category`` column and the frontend. Never
rename them without a migration.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES: list[str] = [
    "organic",
    "paper_cardboard",
    "plastic",
    "metal",
    "glass",
    "e_waste",
    "hazardous",
]

ITEMS: list[str] = [
    # organic
    "food_waste", "eggshells", "coffee_grounds", "tea_bags",
    # paper & cardboard
    "cardboard", "newspaper_magazine", "office_paper",
    # plastic
    "plastic_bottle", "plastic_food_container", "plastic_bag",
    "plastic_cutlery_straw", "plastic_cup_lid", "styrofoam",
    # metal
    "aluminium_can", "steel_food_can",
    # glass
    "glass_bottle", "glass_jar_container",
    # e-waste
    "battery", "mobile_phone", "laptop", "keyboard", "computer_mouse",
    "television", "camera", "microwave", "smartwatch",
    # hazardous
    "aerosol_can",
]

ITEM_TO_CATEGORY: dict[str, str] = {
    "food_waste": "organic", "eggshells": "organic", "coffee_grounds": "organic", "tea_bags": "organic",
    "cardboard": "paper_cardboard", "newspaper_magazine": "paper_cardboard", "office_paper": "paper_cardboard",
    "plastic_bottle": "plastic", "plastic_food_container": "plastic", "plastic_bag": "plastic",
    "plastic_cutlery_straw": "plastic", "plastic_cup_lid": "plastic", "styrofoam": "plastic",
    "aluminium_can": "metal", "steel_food_can": "metal",
    "glass_bottle": "glass", "glass_jar_container": "glass",
    "battery": "e_waste", "mobile_phone": "e_waste", "laptop": "e_waste", "keyboard": "e_waste",
    "computer_mouse": "e_waste", "television": "e_waste", "camera": "e_waste", "microwave": "e_waste",
    "smartwatch": "e_waste",
    "aerosol_can": "hazardous",
}


@dataclass(frozen=True)
class SourceFolder:
    dataset: str          # dataset id (see DATASETS)
    rel_path: str         # folder relative to the raw data root
    category: str | None  # None => excluded from the 7-class task
    item: str | None      # None => no fine-grained label
    role: str = "train"   # "train" (in-distribution) or "ood" (held-out out-of-distribution probe)


# Dataset provenance (documented in docs/ml_documentation.md)
DATASETS = {
    "trashnet": {
        "name": "TrashNet (Thung & Yang, 2016)",
        "url": "https://github.com/garythung/trashnet",
        "license": "MIT",
        "fetch": "https://codeload.github.com/garythung/trashnet/tar.gz/master",
    },
    "garbage12": {
        "name": "Garbage Classification (12 classes), Mostafa Mohamed (Kaggle)",
        "url": "https://www.kaggle.com/datasets/mostafaabla/garbage-classification",
        "license": "ODbL 1.0 (database); image contents (c) original authors, research/education use",
        "fetch": "https://codeload.github.com/aesopdev/garbage_classification_model_smam/tar.gz/HEAD (GitHub mirror, folder extra/large_garb_dataset)",
    },
    "household30": {
        "name": "Recyclable and Household Waste Classification, Alistair King (Kaggle)",
        "url": "https://www.kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification",
        "license": "MIT (Kaggle listing); dataset card: educational, research and non-commercial use, citation required",
        "fetch": "https://codeload.github.com/AyushKumarSD/Recyclable-and-Household-Waste-Classification/tar.gz/HEAD (GitHub mirror)",
    },
    "ewastenet": {
        "name": "E-Waste Vision Dataset (EWasteNet, Islam et al.)",
        "url": "https://github.com/NifulIslam/EWasteNet-A-Two-Stream-DeiT-Approach-for-E-Waste-Classification",
        "license": "No explicit license in repository — academic use with citation",
        "fetch": "https://codeload.github.com/NifulIslam/EWasteNet-A-Two-Stream-DeiT-Approach-for-E-Waste-Classification/tar.gz/HEAD",
    },
}

_TN = "trashnet/data/dataset-resized"
_G12 = "garbage12_mirror/extra/large_garb_dataset"
_H30 = "household30/images"
_EW = "ewastenet/dataset"


def _h30(folder: str, category: str | None, item: str | None, role: str = "train") -> list[SourceFolder]:
    # each household30 class has a studio ("default") and a "real_world" subfolder
    return [
        SourceFolder("household30", f"{_H30}/{folder}/default", category, item, role),
        SourceFolder("household30", f"{_H30}/{folder}/real_world", category, item, role),
    ]


SOURCE_FOLDERS: list[SourceFolder] = [
    # ---------------- TrashNet ----------------
    SourceFolder("trashnet", f"{_TN}/cardboard", "paper_cardboard", "cardboard"),
    SourceFolder("trashnet", f"{_TN}/paper", "paper_cardboard", None),
    SourceFolder("trashnet", f"{_TN}/plastic", "plastic", None),
    SourceFolder("trashnet", f"{_TN}/metal", "metal", None),
    SourceFolder("trashnet", f"{_TN}/glass", "glass", None),
    SourceFolder("trashnet", f"{_TN}/trash", None, None, "ood"),
    # ---------------- Garbage-12 ----------------
    SourceFolder("garbage12", f"{_G12}/biological", "organic", None),
    SourceFolder("garbage12", f"{_G12}/cardboard", "paper_cardboard", "cardboard"),
    SourceFolder("garbage12", f"{_G12}/paper", "paper_cardboard", None),
    SourceFolder("garbage12", f"{_G12}/plastic", "plastic", None),
    SourceFolder("garbage12", f"{_G12}/metal", "metal", None),
    SourceFolder("garbage12", f"{_G12}/brown-glass", "glass", None),
    SourceFolder("garbage12", f"{_G12}/green-glass", "glass", None),
    SourceFolder("garbage12", f"{_G12}/white-glass", "glass", None),
    SourceFolder("garbage12", f"{_G12}/battery", "e_waste", "battery"),
    SourceFolder("garbage12", f"{_G12}/clothes", None, None, "ood"),
    SourceFolder("garbage12", f"{_G12}/shoes", None, None, "ood"),
    SourceFolder("garbage12", f"{_G12}/trash", None, None, "ood"),
    # ---------------- Household-30 ----------------
    *_h30("food_waste", "organic", "food_waste"),
    *_h30("eggshells", "organic", "eggshells"),
    *_h30("coffee_grounds", "organic", "coffee_grounds"),
    *_h30("tea_bags", "organic", "tea_bags"),
    *_h30("cardboard_boxes", "paper_cardboard", "cardboard"),
    *_h30("cardboard_packaging", "paper_cardboard", "cardboard"),
    *_h30("magazines", "paper_cardboard", "newspaper_magazine"),
    *_h30("newspaper", "paper_cardboard", "newspaper_magazine"),
    *_h30("office_paper", "paper_cardboard", "office_paper"),
    *_h30("plastic_water_bottles", "plastic", "plastic_bottle"),
    *_h30("plastic_soda_bottles", "plastic", "plastic_bottle"),
    *_h30("plastic_detergent_bottles", "plastic", "plastic_bottle"),
    *_h30("plastic_food_containers", "plastic", "plastic_food_container"),
    *_h30("plastic_shopping_bags", "plastic", "plastic_bag"),
    *_h30("plastic_trash_bags", "plastic", "plastic_bag"),
    *_h30("disposable_plastic_cutlery", "plastic", "plastic_cutlery_straw"),
    *_h30("plastic_straws", "plastic", "plastic_cutlery_straw"),
    *_h30("plastic_cup_lids", "plastic", "plastic_cup_lid"),
    *_h30("styrofoam_cups", "plastic", "styrofoam"),
    *_h30("styrofoam_food_containers", "plastic", "styrofoam"),
    *_h30("aluminum_soda_cans", "metal", "aluminium_can"),
    *_h30("aluminum_food_cans", "metal", "aluminium_can"),
    *_h30("steel_food_cans", "metal", "steel_food_can"),
    *_h30("glass_beverage_bottles", "glass", "glass_bottle"),
    *_h30("glass_food_jars", "glass", "glass_jar_container"),
    *_h30("glass_cosmetic_containers", "glass", "glass_jar_container"),
    *_h30("aerosol_cans", "hazardous", "aerosol_can"),
    # paper cups are plastic-lined composites (not cleanly one material) and
    # textiles are outside the 7-class taxonomy -> used only as OOD probes
    *_h30("paper_cups", None, None, "ood"),
    *_h30("clothing", None, None, "ood"),
    *_h30("shoes", None, None, "ood"),
    # ---------------- EWasteNet ----------------
    SourceFolder("ewastenet", f"{_EW}/Mobile", "e_waste", "mobile_phone"),
    SourceFolder("ewastenet", f"{_EW}/laptop", "e_waste", "laptop"),
    SourceFolder("ewastenet", f"{_EW}/Keyboards", "e_waste", "keyboard"),
    SourceFolder("ewastenet", f"{_EW}/Mouses", "e_waste", "computer_mouse"),
    SourceFolder("ewastenet", f"{_EW}/TV", "e_waste", "television"),
    SourceFolder("ewastenet", f"{_EW}/camera", "e_waste", "camera"),
    SourceFolder("ewastenet", f"{_EW}/microwave", "e_waste", "microwave"),
    SourceFolder("ewastenet", f"{_EW}/smartwatch", "e_waste", "smartwatch"),
]


def validate_taxonomy() -> None:
    assert len(CATEGORIES) == len(set(CATEGORIES)) == 7
    assert len(ITEMS) == len(set(ITEMS))
    assert set(ITEM_TO_CATEGORY) == set(ITEMS)
    assert set(ITEM_TO_CATEGORY.values()) == set(CATEGORIES)
    for sf in SOURCE_FOLDERS:
        if sf.role == "train":
            assert sf.category in CATEGORIES, sf
            if sf.item is not None:
                assert ITEM_TO_CATEGORY[sf.item] == sf.category, sf
        else:
            assert sf.category is None and sf.item is None, sf


validate_taxonomy()
