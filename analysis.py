import pandas as pd
import altair as alt
import streamlit as st


def analyze_decisions_router(decisions, decision_type_id):
    if not decisions:
        return "Δεν βρέθηκαν δεδομένα για ανάλυση."

    count = len(decisions)
    contract_text = "Πράξη" if count == 1 else "Πράξεις"
    st.markdown(f"### Συγκεντρωτική Ανάλυση {decision_type_id} | Σύνολο: {count} {contract_text}")

    # Λίστα με τύπους που υποστηρίζουν αναζήτηση βάσει ΑΦΜ
    AFM_SUPPORTED_TYPES = ["Δ.1", "Β.4", "Β.2.1", "Β.2.2"]

    # Επιλογή συνάρτησης βάσει τύπου
    if decision_type_id == "Δ.1":
        results_text = analyze_contracts_D1(decisions)
    elif decision_type_id == "Β.4":
        results_text = analyze_donations_B4(decisions)
    elif decision_type_id in ["Β.2.1", "Β.2.2"]:
        results_text = analyze_payments_B2(decisions)
    elif decision_type_id == "Β.5":
        results_text = analyze_grants_B5(decisions)
    elif decision_type_id == "Γ.3.5":
        results_text = analyze_staff_changes_G35(decisions)
    else:
        results_text = "Ο τύπος αυτός δεν υποστηρίζει ακόμη συγκεντρωτική ανάλυση."


    if decision_type_id in AFM_SUPPORTED_TYPES:
        results_text += "\n\n *Μπορείς να πληκτρολογήσεις ένα **ΑΦΜ** από τα παραπάνω για να δεις τις αναλυτικές πράξεις του.*"
    else:
        results_text += "\n\n *Η αναζήτηση βάσει ΑΦΜ δεν υποστηρίζεται για αυτόν τον τύπο πράξεων.*"

    return results_text
def render_analysis_chart(chart_data, y_label, x_label):
    if not chart_data:
        return

    df_plot = pd.DataFrame(chart_data)
    chart = alt.Chart(df_plot).mark_bar().encode(
        y=alt.Y('Entity:N', sort='-x', title=y_label),
        x=alt.X('Value:Q', title=x_label),
        color=alt.value("#1f77b4"),
        tooltip=['Entity', 'Value']
    ).properties(width='container', height=400)

    st.altair_chart(chart, use_container_width=True)


def analyze_contracts_D1(decisions):
    total_amount = 0.0
    vendor_analysis = {}
    type_analysis = {}

    for dec in decisions:
        extra = dec.get('extraFieldValues', {})
        amount = float(extra.get('awardAmount', {}).get('amount', 0.0) or 0.0)
        total_amount += amount

        person_list = extra.get('person', [])
        vendor_name = person_list[0].get('name', 'Άγνωστος Ανάδοχος') if person_list else 'Άγνωστος Ανάδοχος'
        vendor_afm = person_list[0].get('afm', 'Χωρίς ΑΦΜ') if person_list else 'Χωρίς ΑΦΜ'

        vendor_key = (vendor_name, vendor_afm)
        if vendor_key not in vendor_analysis:
            vendor_analysis[vendor_key] = {'total': 0.0, 'count': 0}

        vendor_analysis[vendor_key]['total'] += amount
        vendor_analysis[vendor_key]['count'] += 1

        a_type = extra.get('assignmentType', 'Άγνωστος Τύπος')
        type_analysis[a_type] = type_analysis.get(a_type, 0.0) + amount

    st.markdown(f"### 1. Συνολικό Ποσό Δαπανών: **{total_amount:.2f} EUR**")
    st.markdown("### 2. Ανάλυση ανά Ανάδοχο (Top 10)")

    sorted_vendors = sorted(vendor_analysis.items(), key=lambda x: x[1]['total'], reverse=True)
    chart_data = [{'Entity': k[0], 'Value': v['total']} for k, v in sorted_vendors[:10]]
    render_analysis_chart(chart_data, 'Ανάδοχος', 'Ποσό (€)')

    results_text = ""
    for (name, afm), data in sorted_vendors:
        p_text = "Πράξη" if data['count'] == 1 else "Πράξεις"
        results_text += f"- **{name}** (ΑΦΜ: `{afm}`): {data['count']} {p_text} | **{data['total']:.2f} EUR**\n"

    results_text += "\n### 3. Ανάλυση ανά Τύπο Ανάθεσης\n"
    for t_name, amt in sorted(type_analysis.items(), key=lambda x: x[1], reverse=True):
        results_text += f"- **{t_name}**: **{amt:.2f} EUR**\n"

    return results_text

def analyze_donations_B4(decisions):
    receiver_analysis = {}
    total_amount = 0.0
    for dec in decisions:
        extra = dec.get('extraFieldValues', {})
        amount = float(extra.get('amountWithVAT', {}).get('amount', 0.0) or 0.0)
        total_amount += amount
        receivers = extra.get('donationReceiver', [])
        r_name = receivers[0].get('name', 'Άγνωστος Αποδέκτης') if receivers else 'Άγνωστος Αποδέκτης'
        r_afm = receivers[0].get('afm', 'Χωρίς ΑΦΜ') if receivers else 'Χωρίς ΑΦΜ'

        key = (r_name, r_afm)
        if key not in receiver_analysis:
            receiver_analysis[key] = {'total': 0.0, 'count': 0}
        receiver_analysis[key]['total'] += amount
        receiver_analysis[key]['count'] += 1

    st.markdown(f"### 1. Συνολικό Ποσό: **{total_amount:.2f} EUR**")
    st.markdown("### 2. Ανάλυση ανά Αποδέκτη (Top 10)")

    sorted_data = sorted(receiver_analysis.items(), key=lambda x: x[1]['total'], reverse=True)
    chart_data = [{'Entity': k[0], 'Value': v['total']} for k, v in sorted_data[:10]]
    render_analysis_chart(chart_data, 'Αποδέκτης', 'Ποσό (€)')

    results_text = ""
    for (name, afm), data in sorted_data:
        p_text = "Πράξη" if data['count'] == 1 else "Πράξεις"
        results_text += f"- **{name}** (ΑΦΜ: `{afm}`): {data['count']} {p_text} | **{data['total']:.2f} EUR**\n"
    return results_text

def analyze_payments_B2(decisions):
    sponsor_analysis = {}
    total_amount = 0.0
    for dec in decisions:
        for s in dec.get('extraFieldValues', {}).get('sponsor', []):
            amt = float(s.get('expenseAmount', {}).get('amount', 0.0) or 0.0)
            total_amount += amt
            afm_data = s.get('sponsorAFMName', {})
            key = (afm_data.get('name', 'Άγνωστος Δικαιούχος'), afm_data.get('afm', 'Χωρίς ΑΦΜ'))

            if key not in sponsor_analysis:
                sponsor_analysis[key] = {'total': 0.0, 'count': 0}
            sponsor_analysis[key]['total'] += amt
            sponsor_analysis[key]['count'] += 1

    st.markdown(f"### 1. Συνολικό Ποσό: **{total_amount:.2f} EUR**")
    st.markdown("### 2. Ανάλυση ανά Δικαιούχο (Top 10)")

    sorted_data = sorted(sponsor_analysis.items(), key=lambda x: x[1]['total'], reverse=True)
    chart_data = [{'Entity': k[0], 'Value': v['total']} for k, v in sorted_data[:10]]
    render_analysis_chart(chart_data, 'Δικαιούχος', 'Ποσό (€)')

    results_text = ""
    for (name, afm), data in sorted_data:
        p_text = "Πράξη" if data['count'] == 1 else "Πράξεις"
        results_text += f"- **{name}** (ΑΦΜ: `{afm}`): {data['count']} {p_text} | **{data['total']:.2f} EUR**\n"
    return results_text


def analyze_grants_B5(decisions):
    grantee_analysis = {}
    for dec in decisions:
        grantees = dec.get('extraFieldValues', {}).get('grantee', [])
        g_name = grantees[0].get('name', 'Άγνωστος Φορέας') if grantees else 'Άγνωστος Φορέας'
        grantee_analysis[g_name] = grantee_analysis.get(g_name, 0) + 1

    st.markdown("### Ανάλυση ανά Φορέα Παραχώρησης (Top 10)")
    sorted_data = sorted(grantee_analysis.items(), key=lambda x: x[1], reverse=True)
    chart_data = [{'Entity': k, 'Value': v} for k, v in sorted_data[:10]]
    render_analysis_chart(chart_data, 'Φορέας', 'Πλήθος')

    results_text = ""
    for name, c in sorted_data:
        results_text += f"- **{name}**: {c} παραχωρήσεις\n"
    return results_text


def analyze_staff_changes_G35(decisions):
    type_analysis = {}
    for dec in decisions:
        eidos = dec.get('extraFieldValues', {}).get('eidosYpMetavolis', 'Άγνωστη Μεταβολή')
        type_analysis[eidos] = type_analysis.get(eidos, 0) + 1

    results_text = "### Ανάλυση ανά Είδος Μεταβολής\n"
    for name, c in sorted(type_analysis.items(), key=lambda x: x[1], reverse=True):
        results_text += f"- **{name}**: {c} πράξεις\n"
    return results_text