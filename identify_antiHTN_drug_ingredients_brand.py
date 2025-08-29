import pandas as pd
import requests
import requests_cache
# from concurrent.futures import ThreadPoolExecutor, as_completed
requests_cache.install_cache(cache_name='http_cache',backend='filesystem')

# === Identify antiHTN drug members using RxCUI based on ATC ===
def get_drug_members_by_class(atc_class_id):
    url = "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json"
    params = {"classId": atc_class_id, "relaSource": "ATC"}

    response = requests.get(url, params=params)
    data = response.json()
    # print(data)

    members = data['drugMemberGroup']['drugMember']
    # members = data.get('drugMemberGroup', {}).get('drugMember', {})
    ingredientList = []

    for member in members:
        min_concept = member.get("minConcept", {})
        name = min_concept.get("name")
        ingredientList.append(name)

    # print(ingredientList)
    return ingredientList

def get_rxcui(name):
    url = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
    params = {"name": name, "search": 2}
    r = requests.get(url, params=params)
    data = r.json()
    # return data['idGroup']['rxnormID']
    return data.get("idGroup", {}).get("rxnormId", [None])[0]

def get_synonyms(rxcui):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allProperties.json"
    params = {"prop": "names"}
    r = requests.get(url, params=params)
    data = r.json()
    # print('synonyms: ')
    # print(data)
    synonyms = set()
    for prop in data["propConceptGroup"]["propConcept"]:
    # for prop in data.get("propConceptGroup", {}).get("propConcept", []):
        synonym = prop["propValue"]
        # print(type(synonym))
        synonyms.add(synonym.lower())

    # print("synonyms", synonyms)
    return synonyms


def passes_atc_gate(rxcui):
    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"
    params = {"rxcui": rxcui, "relaSource": "ATC"}
    r = requests.get(url, params=params)
    data = r.json()

    classes = []
    for item in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []) or []:
        cid = item.get("rxclassMinConceptItem", {}).get("classId")
        if item['minConcept']['tty'] == "IN":
            cid = item.get("rxclassMinConceptItem", {}).get("classId")
            if cid:
                classes.append(cid)
    # print('atc code')
    # print(classes)
    # allow only antihypertensives (C02, C03, C07, C08, C09)
    # exclude C09D combos and dermatology (D..)
    if any(cid.startswith("C02KX") for cid in classes):  # exclude pulmonary hypertension
        return False
    if any(cid.startswith("C09XX") for cid in classes):
        return False
    if any(cid.startswith("C09DX") for cid in classes):
        return False
    if any(cid[0] == "D" for cid in classes):  # exclude dermatology e.g. hair minoxidil
        return False

    # if any(cid[:4] in {"C02A","C02B","C02C","C02D","C02K","C03A","C03B","C03C","C03D","C03E",
    #                    "C07A","C08C","C08D","C08E","C09A","C09C","C09X"} for cid in classes):
    if any(cid[:3] in {"C02", "C03", "C07", "C08", "C09"} for cid in classes):
        return True

    return False

def build_all_ingredient_list(ingredient_list):
    # all_names = set()
    name_to_rxcui_dict = {}
    for name in ingredient_list:
        # print('ingredient name')
        # print(name)
        rxcui = get_rxcui((name))
        if not rxcui:
            print(f" No RxCUI found for {name}")
            continue

        if passes_atc_gate(rxcui):
            name_to_rxcui_dict[name] = rxcui

            synonyms = get_synonyms(rxcui)
            # all_names.update(synonyms)
            for syn in synonyms:
                syn_rxcui = get_rxcui(syn)
                if syn_rxcui and passes_atc_gate(syn_rxcui):
                    # all_names.add(syn.lower())
                    name_to_rxcui_dict[syn] = syn_rxcui

    return name_to_rxcui_dict

DISALLOWED_FORMS = (
    "ophthalmic", "eye", "otic", "topical", "patch", "transdermal",
    "injection", "intravenous", "iv", "intramuscular", "subcutaneous",
    "inhalation", "nasal", "rectal", "vaginal", "buccal", "sublingual",
    "irrigation", "spray", "drops", "solution", "suspension", "elixir",
    "gel", "lotion", "cream", "ointment", "foam", "paste", "liquid"
)

ALLOWED_FORMS = ("capsule", "tablet")

# find obsolete brands from the ingredient list
def fetch_all_brand(status:str):

    url1 = "https://rxnav.nlm.nih.gov/REST/allstatus.json"
    params1 = {"status": status}
    r1 = requests.get(url1, params=params1)
    data1 = r1.json()
    # print(data1)
    out = []
    out1 = []

    for d1 in data1['minConceptGroup']['minConcept']:

        if d1['tty'] == 'BN':
            out.append((d1.get("name"), d1.get('rxcui')))
            # i = i + 1
        if d1['tty'] == 'SBD':
            out1.append((d1.get("name"), d1.get('rxcui')))  ## list with SBD [ingredient + dosage form + [brandname]
    kept_brand = []

    for brand, brand_rx in out:

        brand_matched_sbd = [sbd_name for sbd_name, _ in out1 if brand in sbd_name]
        # print(brand_matched_sbd)
        if not brand_matched_sbd:
            # dropped_brand.append((brand, brand_rx))
            continue

        has_allowed = False
        has_disallowed = False

        for sbd in brand_matched_sbd:
            sbd_low = sbd.lower()
            if any(form in sbd_low for form in DISALLOWED_FORMS):
                has_disallowed = True
            if any(term in sbd_low for term in ALLOWED_FORMS):
                has_allowed = True

        if has_allowed and has_disallowed:
            kept_brand.append((brand, brand_rx))
        elif has_allowed and not has_disallowed:
            kept_brand.append((brand, brand_rx))
        elif not has_allowed and has_disallowed:
            continue

    return kept_brand #a list of (bn_rxcui, brand_name) pairs.

# for each brand, call historystatus to look for their main ingredient
def bn_ingredients(bn_rxcui: str)->list:
    url1 = f"https://rxnav.nlm.nih.gov/REST/rxcui/{bn_rxcui}/historystatus.json"
    rel_in = requests.get(url1).json()
    # print(rel_in)
    ing_list = []

    dc = rel_in.get('rxcuiStatusHistory', {}).get('derivedConcepts', {}) or {}
    ings = dc.get('ingredientConcept') or []
    for i in ings:
        rx = i.get('ingredientRxcui') or ""
        ingredient_name = i.get('ingredientName') or ""

        ing_list.append((rx, ingredient_name))

    # print(ings)
    return ing_list # a list of ingredients (in tuples) for that particular brand

def find_brands_for_ingredients(all_ingredient_dic: dict, status:str)->dict:
    bn_list = fetch_all_brand(status) # [(bn_rxcui, bn_name), ...] in a list of tuples
    brands_dict = {}
    all_ingredient_rxcui_list = list(all_ingredient_dic.values())
    all_ingredient_rxcui_list = {str(x) for x in all_ingredient_rxcui_list}

    for bn_name, bn_rx in bn_list:
        hit_found = False
        ingredient_list_in_brand = bn_ingredients(bn_rx)
        all_ingredient_ID = [ing_id for ing_id, ing_name in ingredient_list_in_brand]
        # print(all_ingredient_ID)
        all_ingredient_name = [ing_name for ing_id, ing_name in ingredient_list_in_brand]

        hit_found = any(ing_ids in all_ingredient_rxcui_list for ing_ids in all_ingredient_ID)
        if hit_found:
            brands_dict[bn_name] = {
                "name": bn_name.lower(),
                "rxcui": bn_rx,
                "minIngredients_ID": all_ingredient_ID,
                "minIngredients_name": all_ingredient_name,
                "status": status
            }

    return brands_dict


def main():
    ## STEP 1: Identify all ingredients for antihypertensive medications
    atc_classes = ['C02', 'C03', 'C07', 'C08', 'C09']  # ATC codes for antihypertensives
    all_names = set()

    for class_id in atc_classes:
        print(f"Fetching drugs from ATC: {class_id}")
        class_names = get_drug_members_by_class(class_id)
        all_names.update(class_names)
    # print(all_names) # set of all antihypertensive ingredients
    ingredient_set = set()

    for name in all_names:
        name = name.replace("/", ",")
        ingredients = [part.strip() for part in name.split(",") if part.strip()]
        ingredient_set.update(ingredients)
    ingredients_sorted = sorted(ingredient_set) # set of all normalized antihypertensive ingredients
    # print(ingredients_sorted)

    # Step 2: After identifying ingredients, looking through RxNORM database to find their ID and other potential ingredient name
    all_ingredient_list_dict = build_all_ingredient_list(ingredients_sorted)
    # print(all_ingredient_list)

    # Step 3: find active brand name
    active_brand_dict = find_brands_for_ingredients(all_ingredient_list_dict, status="active")

    # Step 4: find obsolete brand from ingredient
    obsolete_brand_dict = find_brands_for_ingredients(all_ingredient_list_dict, status="obsolete")

    # Step 5: combine both active and obsolete brand dictionaries
    # Create DataFrames separately
    df = pd.DataFrame.from_dict(all_ingredient_list_dict, orient='index')
    df.columns = ['rxcui']
    df = df.reset_index().rename(columns={"index": "name"})
    df["status"] = "ingredient"
    df = df[['name', 'rxcui', 'status']]

    df1 = pd.DataFrame.from_dict(active_brand_dict, orient="index")
    df1 = df1[["name", "rxcui", "status"]]
    df2 = pd.DataFrame.from_dict(obsolete_brand_dict, orient="index")
    df2 = df2[["name", "rxcui", "status"]]

    # Combine
    df_comb = pd.concat([df, df1, df2])

    pd.DataFrame(df_comb).to_csv("antiHTN_drug_allBRANDs_ingredients_list.csv",index=False)

if __name__ == "__main__":
    main()




