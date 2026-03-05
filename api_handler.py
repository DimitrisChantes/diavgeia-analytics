import requests
import streamlit as st
from urllib.parse import quote
from helpers import stem_tokens

@st.cache_data(show_spinner="🔄 Φόρτωση οργανισμών από ΔΙΑΥΓΕΙΑ... παρακαλώ περιμένετε")
def fetch_organizations():
    url = "https://diavgeia.gov.gr/opendata/organizations"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("organizations", [])
    return []


@st.cache_data(show_spinner="🔄 Φόρτωση τύπων αποφάσεων... παρακαλώ περιμένετε")
def fetch_decision_types_filtered():
    url = "https://diavgeia.gov.gr/opendata/types"
    try:
        response = requests.get(url)
        if response.ok:
            all_types = response.json().get("decisionTypes", [])
            # Κράτα μόνο όσα έχουν parent
            filtered = [t for t in all_types if t.get("parent")]
            for t in filtered:
                t["display"] = f"[{t['uid']}] {t['label']}"
            filtered.sort(key=lambda x: x["uid"])
            return filtered
    except:
        pass
    return []

def search_organizations(user_input, organizations, min_common_stems=2):
    input_stems = stem_tokens(user_input)
    matches = []
    for org in organizations:
        org_stems = stem_tokens(org['label'])
        common = input_stems & org_stems
        if len(common) >= min_common_stems:
            matches.append(org)
    if not matches:
        for org in organizations:
            org_stems = stem_tokens(org['label'])
            common = input_stems & org_stems
            if len(common) >= 1:
                matches.append(org)
    return matches

def fetch_decision_count(uid, from_date=None, to_date=None, decision_type_uid=None):
    base_url = f"https://diavgeia.gov.gr/opendata/search.json?org={uid}&size=1"
    if from_date:
        base_url += f"&from_issue_date={from_date.strftime('%Y-%m-%d')}"
    if to_date:
        base_url += f"&to_issue_date={to_date.strftime('%Y-%m-%d')}"
    if decision_type_uid:
        encoded_type = quote(decision_type_uid)
        base_url += f"&type={encoded_type}"

    try:
        response = requests.get(base_url)
        if response.ok:
            data = response.json()
            total = data.get("info", {}).get("total", 0)
            return total
        else:
            pass

    except Exception as e:
        pass
    return 0

def fetch_decisions_by_uid(uid, from_date=None, to_date=None, page=0, size=100, decision_type_uid=None):
    base_url = f"https://diavgeia.gov.gr/opendata/search.json?org={uid}&page={page}&size={size}"
    if from_date:
        base_url += f"&from_issue_date={from_date.strftime('%Y-%m-%d')}"
    if to_date:
        base_url += f"&to_issue_date={to_date.strftime('%Y-%m-%d')}"
    if decision_type_uid:
        encoded_type = quote(decision_type_uid)
        base_url += f"&type={encoded_type}"
    print(base_url)
    response = requests.get(base_url)
    if response.status_code == 200:
        return response.json().get("decisions", [])
    return []

def fetch_all_decisions(uid, from_date=None, to_date=None, decision_type_uid=None, max_decisions=5000):
    total = fetch_decision_count(uid, from_date, to_date, decision_type_uid)
    total_to_fetch = min(total, max_decisions)
    decisions = []
    page_size = 100

    if total == 0:
        return []

    num_pages = (total_to_fetch + page_size - 1) // page_size

    for page in range(num_pages):
        page_decisions = fetch_decisions_by_uid(
            uid,
            from_date=from_date,
            to_date=to_date,
            page=page,
            size=page_size,
            decision_type_uid=decision_type_uid
        )
        decisions.extend(page_decisions)

        if len(decisions) >= total_to_fetch or not page_decisions:
            break

    return decisions

def get_signer_names(signer_ids):
    results = []
    for signer_id in signer_ids:
        url = f"https://diavgeia.gov.gr/opendata/signers/{signer_id}.json"
        try:
            response = requests.get(url)
            if response.ok:
                data = response.json()
                full_name = f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
                positions = [unit.get('positionLabel') for unit in data.get('units', []) if unit.get('positionLabel')]
                label = f"{full_name} ({', '.join(positions)})" if positions else f"{full_name} (χωρίς θέση)"
                results.append(label)
            else:
                results.append(f"Άγνωστος υπογράφων ({signer_id})")
        except Exception as e:
            results.append(f"Σφάλμα για {signer_id}: {e}")
    return results

def fetch_organization_label(org_id):
    url = f"https://diavgeia.gov.gr/luminapi/opendata/organizations/{org_id}.json"
    try:
        resp = requests.get(url)
        if resp.ok:
            data = resp.json()
            return data.get('label', 'Άγνωστος οργανισμός')
    except:
        pass
    return "Άγνωστος οργανισμός"

