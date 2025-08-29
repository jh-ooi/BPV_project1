## after extracting all the potential antihypertensive drugs (generic/brand name/ingredient)
## make sure all are antihypertensive drugs and map the drug names into respective drug class and regimen type


import pandas as pd
import requests
import requests_cache
requests_cache.install_cache(cache_name='http_cache',backend='filesystem')
from typing import Set, Tuple

# == Ingredient --> Class mapping ==
def get_atc_id(rxcui_id: str):

    atc_id = set()
    ing_name_set = set()
    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"
    params = {"rxcui": rxcui_id, "relaSource": "ATC"}
    r = requests.get(url, params=params)
    data = r.json()

    for classDrug in data.get('rxclassDrugInfoList', {}).get('rxclassDrugInfo', []):
        ingredient_type = classDrug.get("minConcept").get("tty")
        # print(ingredient_type)
        if ingredient_type == "IN":
            minConceptItem = classDrug.get("rxclassMinConceptItem", {})
            # print(minConcept)
            ATC_classID = minConceptItem.get("classId")
            # if is_target_antihypertensive((ATC_classID)):
            ingredientName = classDrug.get("minConcept").get("name")

            if ATC_classID:
                atc_id.add((ingredientName, ATC_classID))
            # print(ATC_classID)
            # ingredientID = classDrug.get("minConcept").get("rxcui")

            # print(ingredientName)
            # print(ATC_classID)

            # if ATC_classID and is_target_antihypertensive(ATC_classID):
                # ing_name_set.add(ingredientName)
                # atc_id.add((ingredientName, ATC_classID))
                # print(f"name: {name}")
                # print(f"classID: {classID}")

    # fallback: if no IN entries, try PIN (precise ingredient)
    if not atc_id:
        # print("hh")
        for classDrug in data.get('rxclassDrugInfoList', {}).get('rxclassDrugInfo', []):
            ingredient_type = classDrug.get("minConcept").get("tty")
            # print(ingredient_type)
            if ingredient_type == "PIN":
                minConceptItem = classDrug.get("rxclassMinConceptItem", {})
                ATC_classID = minConceptItem.get("classId")
                # if is_target_antihypertensive((ATC_classID)):
                ingredientName = classDrug.get("minConcept").get("name")
                if ATC_classID:
                    atc_id.add((ingredientName, ATC_classID))

    # print(atc_id)
    # return ing_name_set, atc_id
    return atc_id if atc_id else ()

def get_atc_for_brand_rxcui(brand_rxcui: str):
    ing_list = []
    final_ing = set()
    all_classId = set()

    url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{brand_rxcui}/historystatus.json"
    rel_in = requests.get(url).json()

    dc = rel_in.get('rxcuiStatusHistory', {}).get('derivedConcepts', {}) or {}
    ings = dc.get('ingredientConcept') or []

    for i in ings:
        rx = i.get('ingredientRxcui') or ""
        ingredient_name = i.get('ingredientName') or ""
        ing_list.append((rx, ingredient_name))
        # final_ing.add(ingredient_name)

    for ing_ID, ing_Name in ing_list:
        ingName_ATC_code = get_atc_id(ing_ID)
        # ingName_ATC_code = filter_atc(ing_Name, classID)
        # print(classID)
        # print(type(classID))
        # final_ing.update(ingredient_NAMESET)
        all_classId.update(ingName_ATC_code)


    return all_classId if all_classId else ()

def keep_brand(pairs):
    ingredients = {name for name, _ in pairs}
    for ing in ingredients:
        atcs_for_ing = [a for n, a in pairs if n == ing]
        if not any(is_target_antihypertensive(a) for a in atcs_for_ing):
            return False
    return True

def is_target_antihypertensive(atc_id) -> bool:
    if atc_id.startswith(("C02A", "C02B", "C02C", "C02D", "C02K", "C03A", "C03B",
                          "C03C", "C03D", "C03E","C07A", "C08C", "C08D", "C08E",
                          "C09A", "C09C", "C09X")):
        return True
    if atc_id.startswith("C02KX"):
        return False
    if atc_id.startswith("C09XX"):
        return False

    return False

def regimen_type(ingredients: set[str]) -> str:
    # Count unique ingredients
    count = len(set(ingredients))
    if count == 1:
        return "monotherapy"
    elif count == 2:
        return "combination of 2 drugs"
    elif count == 3:
        return "combination of 3 drugs"
    elif count == 4:
        return "combination of 4 drugs"
    else:
        return "combination of > 5 drugs"

# map to drug class - from ATC code to drug Class
ATC_to_class_dict = {"C09A": "ACEi", "C09C": "ARB", "C09X": "Other RAS",
                "C08C": "CCB", "C08D": "CCB", "C08E": "CCB",
                "C07A": "Beta-Blocker",
                "C03A": "Diuretics: thiazide", "C03B": "Diuretics: non-thiazide", "C03C": "Diuretics: loop diuretics",
                "C03D": "Diuretics: potassium-sparing agent", "C03E": "Diuretics: potassium-sparing agent combination",
                "C02A": "Other: centrally acting", "C02B": "Other: ganglion blocking", "C02C": "Other: peripherally acting (alpha)",
                "C02D": "Other: vasodilator", "C02K": "Other"
                }

def class_from_ATC(ATC: set)->set:
    results = set()
    for code in ATC:
        drugClass = ATC_to_class_dict.get(code[:4], "Not target antihypertensives")
        # print(drugClass)
        # print(type(drugClass))
        results.add(drugClass)
        # print (results)
    return results


def main():
    # === load the RxNorm potential antiHTN drug list ===
    df = pd.read_csv("antiHTN_drug_allBRANDs_ingredients_list.csv", low_memory=False)
    # OBJECT_NAME = df['name']
    # OBJECT_RXCUI = df['rxcui']
    # OBJECT_STATUS = df['status']

    kept_rows = []

    for _, row in df.iterrows():
        obj_rxcui = row["rxcui"]
        obj_status = row["status"]
        # print(f"{obj_rxcui}: {obj_status}")

        if obj_status in ("active", "obsolete"):
            ING_NAME_ATC_PAIRS = get_atc_for_brand_rxcui(obj_rxcui)

        elif obj_status == "ingredient":
            ING_NAME_ATC_PAIRS = get_atc_id(obj_rxcui)

        # print(ING_NAME_ATC_PAIRS)
        # print(obj_rxcui)

        if ING_NAME_ATC_PAIRS:
            if keep_brand(ING_NAME_ATC_PAIRS):

                ING_NAME = {name for name, _ in ING_NAME_ATC_PAIRS}
                ING_ATC_ID = {atc for _, atc in ING_NAME_ATC_PAIRS if is_target_antihypertensive(atc)}

                regimen = regimen_type(ING_NAME)
                drug_class = class_from_ATC(ING_ATC_ID)

                # if any(is_target_antihypertensive(ing_atc_id) for ing_atc_id in ING_ATC_ID):
                kept_rows.append({
                    "name": row["name"],
                    "rxcui": row["rxcui"],
                    "status": row["status"],
                    "ingredient": ", ".join(sorted(ING_NAME)) if ING_NAME else "",
                    "ATC_code": ", ".join(sorted(ING_ATC_ID)) if ING_ATC_ID else "",
                    "drugClass": ", ".join(sorted(drug_class)) if drug_class else "",
                    "regimen": regimen
                })

    df_kept = pd.DataFrame(kept_rows)
    df_kept.to_csv("antiHTN_drug_filtered_MAPPING.csv", index=False)

if __name__ == "__main__":
    main()
    # ING_NAME_ATC_PAIRS = get_atc_for_brand_rxcui(140587)
    # print(ING_NAME_ATC_PAIRS)
    # ING_NAME_ATC_PAIRS = get_atc_for_brand_rxcui(303838)
    # print(ING_NAME_ATC_PAIRS)
    # ING_NAME, ING_ATC_ID = set(zip(*ING_NAME_ATC_PAIRS))
    # print(ING_NAME)
    # print(ING_ATC_ID)
    # print('------')
    # ING_NAME_ATC_PAIRS = get_atc_id(140587)
    # print(ING_NAME_ATC_PAIRS)
    # if ING_NAME_ATC_PAIRS:
    #     ING_NAME = {name for name, _ in ING_NAME_ATC_PAIRS}
    #     ING_ATC_ID = {atc for _, atc in ING_NAME_ATC_PAIRS}
    # print('final')
    # print(ING_NAME)
    # print(ING_ATC_ID)
