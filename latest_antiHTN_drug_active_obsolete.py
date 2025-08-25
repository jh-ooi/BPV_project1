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
        if cid:
            classes.append(cid)
    # print('atc code')
    # print(classes)
    # allow only antihypertensives (C02, C03, C07, C08, C09)
    # exclude C09D combos and dermatology (D..)
    if any(cid.startswith("C02KX") for cid in classes):  # exclude Entresto, etc.
        return False
    # if any(cid.startswith("C09D") for cid in classes):
    #     return False
    if any(cid[0] == "D" for cid in classes):  # exclude dermatology e.g. hair minoxidil
        return False

    # if any(cid[:4] in {"C02A","C02B","C02C","C02D","C02K","C03A","C03B","C03C","C03D","C03E",
    #                    "C07A","C08C","C08D","C08E","C09A","C09C","C09X"} for cid in classes):
    if any(cid[:3] in {"C02", "C03", "C07", "C08", "C09"} for cid in classes):
        return True


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
        # if passes_atc_gate(rxcui):
        #     all_names.add(name)
        #     print("22")
        # print(all_names)
        # all_names.add(name)
        name_to_rxcui_dict[name] = rxcui

        synonyms = get_synonyms(rxcui)
        # all_names.update(synonyms)
        for syn in synonyms:
            syn_rxcui = get_rxcui(syn)
            if syn_rxcui and passes_atc_gate(syn_rxcui):
                # all_names.add(syn.lower())
                name_to_rxcui_dict[syn] = syn_rxcui


    return name_to_rxcui_dict

def get_active_brand_name_from_all_ingredient_list(ingredient_list: dict)->dict:
    # brands = set()
    brand_dict = {}
    for ing_name, ing_rxcui in ingredient_list.items():
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{ing_rxcui}/related.json"
        # print(url)
        params = {"tty": "BN"}
        r = requests.get(url, params=params)
        data = r.json()
        # print(data)


        for group in data.get("relatedGroup", {}).get("conceptGroup", []):
            for concept in group.get("conceptProperties", []):
                name1 = concept.get("name")
                brand_rxcui = concept["rxcui"]
                # brands.add(name1.lower())
                # brand_dict[name1] = brand_rxcui
                brand_dict[name1] = {
                    "name": name1,
                    "rxcui": brand_rxcui,
                    # "minIngredients_ID": all_ingredient_ID,
                    # "minIngredients_name": all_ingredient_name,
                    "status": "active"
                }

    print(brand_dict)
    return brand_dict

# find obsolete brands from the ingredient list
def fetch_all_obsolete_brand():
    # for those obsolete
    url1 = "https://rxnav.nlm.nih.gov/REST/allstatus.json"
    params1 = {"status": "obsolete"}
    r1 = requests.get(url1, params=params1)
    data1 = r1.json()
    # print(data1)
    out = []
    i = 1

    for d1 in data1['minConceptGroup']['minConcept']:

        if d1['tty'] == 'BN':
            out.append((d1.get("name"), d1.get('rxcui')))
            i = i + 1
    # print(out)
    return out #a list of (bn_rxcui, brand_name) pairs.

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
        # print('1')
        # print(rx)
        # print(ingredient_name)
        ing_list.append((rx, ingredient_name))

    # print(ings)
    return ing_list # a list of ingredients (in tuples) for that particular brand

def find_obsolete_brands_for_ingredients(all_ingredient_dic: dict)->dict:
    bn_list = fetch_all_obsolete_brand() # [(bn_rxcui, bn_name), ...] in a list of tuples
    # print('a')
    # print(bn_list)
    obso_brands_dict = {}
    all_ingredient_rxcui_list = list(all_ingredient_dic.values())
    all_ingredient_rxcui_list = {str(x) for x in all_ingredient_rxcui_list}

    for bn_name, bn_rx in bn_list:
        hit_found = False
        ingredient_list_in_brand = bn_ingredients(bn_rx)
        all_ingredient_ID = [ing_id for ing_id, ing_name in ingredient_list_in_brand]
        # print(all_ingredient_ID)
        all_ingredient_name = [ing_name for ing_id, ing_name in ingredient_list_in_brand]

        hit_found = any(ing_id in all_ingredient_rxcui_list for ing_id in all_ingredient_ID)
        if hit_found:
            obso_brands_dict[bn_name] = {
                "name": bn_name,
                "rxcui": bn_rx,
                "minIngredients_ID": all_ingredient_ID,
                "minIngredients_name": all_ingredient_name,
                "status": "obsolete"
            }

    return obso_brands_dict

    # for bn_rx, bn_name in bn_list:
    #     ingredient_list_in_brand = bn_ingredients(bn_rx)
    #
    #     for ingredient_ID, ingredient_name in ingredient_list_in_brand:
    #         # print(ingredient_ID, ingredient_name)
    #         if ingredient_ID in ingredient_rxcui_set:
    #
    #             bn_detail[bn_rx] = {
    #                 "brand_name": bn_name,
    #                 "brand_rxcui": bn_rx,
    #                 "minIngredients_ID": ingredient_ID,
    #                 "minIngredients_name": ingredient_name,
    #             }
    #
    #             obsolete_brands_list.append((bn_name, bn_rx))
    #     # print(bn_detail)

def main():
    ## STEP 1: Identify all ingredients for antihypertensive medications
    atc_classes = ['C02', 'C03', 'C07', 'C08', 'C09']  # ATC codes for antihypertensives
    # atc_classes = ['C07']  # ATC codes for antihypertensives
    all_names = set()

    for class_id in atc_classes:
        print(f"Fetching drugs from ATC: {class_id}")
        class_names = get_drug_members_by_class(class_id)
        all_names.update(class_names)
    print(all_names) # set of all antihypertensive ingredients
    ingredient_set = set()

    for name in all_names:
        name = name.replace("/", ",")
        ingredients = [part.strip() for part in name.split(",") if part.strip()]
        ingredient_set.update(ingredients)
    ingredients_sorted = sorted(ingredient_set) # set of all normalized antihypertensive ingredients
    print(ingredients_sorted)

    # Step 2: After identifying ingredients, looking through RxNORM database to find their ID and other potential ingredient name
    all_ingredient_list_dict = build_all_ingredient_list(ingredients_sorted)
    # print(all_ingredient_list)

    # Step 3: find active brand name
    active_brand_dict = get_active_brand_name_from_all_ingredient_list(all_ingredient_list_dict)


    # Step 4: find obsolete brand from ingredient
    obsolete_brand_dict = find_obsolete_brands_for_ingredients(all_ingredient_list_dict)

    # Step 5: combine both active and obsolete brand dictionaries
    # Create DataFrames separately
    df = pd.DataFrame.from_dict(all_ingredient_list_dict, orient='index')
    df.columns = ['rxcui']
    df = df.reset_index().rename(columns={"index": "name"})
    df["status"] = ""
    df = df[['name', 'rxcui', 'status']]

    print(df)
    df1 = pd.DataFrame.from_dict(active_brand_dict, orient="index")
    df1 = df1[["name", "rxcui", "status"]]
    df2 = pd.DataFrame.from_dict(obsolete_brand_dict, orient="index")
    df2 = df2[["name", "rxcui", "status"]]
    print(df2)
    # Combine
    df_comb = pd.concat([df, df1, df2])
    print(df_comb)
    pd.DataFrame(df_comb).to_csv("antiHTN_drug_allBRANDs_ingredients_list.csv",index=False)

if __name__ == "__main__":
    main()




