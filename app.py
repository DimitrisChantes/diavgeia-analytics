import streamlit as st
import requests
from datetime import datetime
from urllib.parse import quote
from dateutil.relativedelta import relativedelta
from dateutil import parser as date_parser

from helpers import (
    is_ada, format_date, fetch_dates_from_user,
    format_extra_fields, is_uid
)
from api_handler import (
    fetch_organizations, fetch_decision_types_filtered,
    search_organizations, fetch_decisions_by_uid,
    fetch_decision_count, fetch_all_decisions,
    get_signer_names, fetch_organization_label
)
from analysis import (
    analyze_decisions_router
)

# Καθορισμός των τύπων που υποστηρίζουν ανάλυση
ANALYSIS_TYPES = ["Δ.1", "Β.4", "Β.5", "Β.2.1", "Β.2.2", "Γ.3.5"]


def get_user_input(st_state, user_input_text):

    current_step = st_state.chat_step
    if current_step == "awaiting_dates":

        # Προσπάθεια να κάνουμε parse την ημερομηνία ΑΠΟ
        try:
            if user_input_text.strip():
                st_state.from_date = date_parser.parse(user_input_text.strip(), dayfirst=True).date()
                st_state.last_from_date_input = user_input_text.strip()
            else:
                st_state.last_from_date_input = ""

            st_state.last_to_date_input = ""
            st_state.chat_step = "awaiting_to_date"

            # Υπολογισμός της μέγιστης επιτρεπτής ημερομηνίας 'Έως' για ενημέρωση
            max_to_date_info = st_state.from_date + relativedelta(months=+6)

            return "awaiting_to_date", (
                f"Ημερομηνία Από: **{format_date(datetime.combine(st_state.from_date, datetime.min.time()))}**.\n\n"
                f"Ποια είναι η **ΤΕΛΙΚΗ** ημερομηνία (Έως); \n"
                f"*(Πρέπει να είναι το πολύ 6 μήνες μετά: Έως **{format_date(datetime.combine(max_to_date_info, datetime.min.time()))}**)*\n\n"
                f" (Πληκτρολόγησε την ημερομηνία σε μορφή `ΗΗ/ΜΜ/ΕΕΕΕ`.)"
            )
        except Exception:
            return "awaiting_dates", "Άκυρη μορφή ημερομηνίας 'Από'. Δώσε την ημερομηνία σε μορφή `ΗΗ/ΜΜ/ΕΕΕΕ`."

    elif current_step == "awaiting_to_date":

        # Η ημερομηνία 'Από' (from_date) έχει ήδη καθοριστεί και είναι στο st_state.from_date

        to_date_str = user_input_text.strip()

        try:
            new_from_date, new_to_date = fetch_dates_from_user(

                from_date_str="",
                to_date_str=to_date_str,
                from_date_default=st_state.from_date,
                to_date_default=st_state.to_date
            )

            st_state.from_date = new_from_date
            st_state.to_date = new_to_date

            return "dates_complete", f"Ημερομηνία Έως: **{format_date(datetime.combine(st_state.to_date, datetime.min.time()))}**.\n\n**Οι ημερομηνίες είναι έγκυρες!**"

        except ValueError as e:
            st_state.chat_step = "awaiting_to_date"

            # Υπολογισμός της μέγιστης επιτρεπτής ημερομηνίας 'Έως' για ενημέρωση
            max_to_date_info = st_state.from_date + relativedelta(months=+6)

            return "awaiting_to_date", (
                f"**ΣΦΑΛΜΑ**: {e}\n\n"
                f"Η ημερομηνία 'Από' παραμένει **{format_date(datetime.combine(st_state.from_date, datetime.min.time()))}**."
                f" Δώσε νέα **ΤΕΛΙΚΗ** ημερομηνία (Έως), με διαφορά **έως 6 μήνες** από την 'Από'. (Μέγιστη: **{format_date(datetime.combine(max_to_date_info, datetime.min.time()))}**)"
            )
        except Exception:

            st_state.chat_step = "awaiting_to_date"

            # Υπολογισμός της μέγιστης επιτρεπτής ημερομηνίας 'Έως' για ενημέρωση
            max_to_date_info = st_state.from_date + relativedelta(months=+6)

            return "awaiting_to_date", (
                f"Άκυρη μορφή ημερομηνίας 'Έως'. Δώσε την ημερομηνία σε μορφή `ΗΗ/ΜΜ/ΕΕΕΕ`."
                f" (Η ημερομηνία 'Από' είναι: **{format_date(datetime.combine(st_state.from_date, datetime.min.time()))}** | Μέγιστη 'Έως': **{format_date(datetime.combine(max_to_date_info, datetime.min.time()))}**)"
            )

    return current_step, ""  # Fallback


def parse_diaugeia_act(data):
    def fmt(val):
        # Εξασφαλίζει την εμφάνιση '-' αν η τιμή είναι None/κενή
        return val if val else "–"

    out = []

    extra = data.get("extraFieldValues", {})
    doc_type_id = data.get("decisionTypeId")
    org_label = fetch_organization_label(data.get("organizationId", "-"))

    #Βασικές Πληροφορίες
    out.append("### Βασικές Πληροφορίες Απόφασης\n")
    out.append(f"**Θέμα:** {fmt(data.get('subject', 'Χωρίς θέμα'))}  \n")
    out.append(f"**ΑΔΑ:** {fmt(data.get('ada'))}  \n")
    out.append(f"**Ημερομηνία Έκδοσης:** {format_date(data.get('issueDate', 0))}  \n")
    out.append(f"**Τύπος Απόφασης (ID):** **{doc_type_id}** \n")
    out.append(f"**Οργανισμός:** {org_label}  \n")
    out.append(f"**Κατάσταση:** {fmt(data.get('status'))}  \n")
    out.append(f"---  ")

    #extraFieldValues
    if extra:
        out.append("\n### Εξειδικευμένα Στοιχεία")
        out.extend(format_extra_fields(extra))
        out.append("---  ")

    # Υπογράφοντες
    signer_ids = data.get("signerIds", [])
    if signer_ids:
        signers = get_signer_names(signer_ids)
        out.append("**Υπογράφοντες:** ")
        for s in signers:
            out.append(f"- {s}  ")
    else:
        out.append("**Υπογράφοντες:** –  ")

    #PDF έγγραφο
    if data.get("documentUrl"):
        out.append("\n---  ")
        out.append(f"[ Προβολή πλήρους εγγράφου (PDF)]({data.get('documentUrl')})  ")

    return "\n".join(out)



st.set_page_config(page_title="Αναζήτηση - ΔΙΑΥΓΕΙΑ", page_icon="🏛️")
st.title("🔍 Αναζήτηση στην ΔΙΑΥΓΕΙΑ")

# Φόρτωση οργανισμών
if "orgs_loaded" not in st.session_state:
    st.session_state.organizations = fetch_organizations()
    st.session_state.orgs_loaded = True
    st.session_state.decision_types = fetch_decision_types_filtered()

organizations = st.session_state.organizations
decision_types = st.session_state.decision_types


if "messages" not in st.session_state:
    st.session_state.messages = []


    st.session_state.selected_org_uid = None
    st.session_state.selected_type_uid = None
    st.session_state.selected_type_label = "Όλοι οι τύποι"


    today = datetime.today()

    default_from_date = today.date() - relativedelta(months=6)

    st.session_state.from_date = default_from_date
    st.session_state.to_date = today.date()


    st.session_state.last_from_date_input = ""
    st.session_state.last_to_date_input = ""


    st.session_state.chat_step = "awaiting_org"
    st.session_state.current_page = 0
    st.session_state.page_size = 100
    st.session_state.total_decisions = 0
    st.session_state.current_decisions = []
    st.session_state.current_index = 0


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


user_input = st.chat_input("Πληκτρολόγησε οργανισμό, uid ή ΑΔΑ")
if user_input:

    st.markdown('<div id="chat_end"></div>', unsafe_allow_html=True)

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Επεξεργασία..."):
            text = user_input.strip()
            response_text = ""


            if text.isdigit() and len(text) == 9:
                if st.session_state.last_analysis_decisions:
                    entries_found = []
                    for d in st.session_state.last_analysis_decisions:
                        extra = d.get('extraFieldValues', {})

                        # Α. Έλεγχος σε Αναδόχους (για Δ.1)
                        for p in extra.get('person', []):
                            if p.get('afm') == text:
                                entries_found.append({
                                    'subject': d.get('subject'),
                                    'ada': d.get('ada'),
                                    'date': d.get('issueDate'),
                                    'amount': extra.get('awardAmount', {}).get('amount', '0')
                                })


                        for s in extra.get('sponsor', []):
                            if s.get('sponsorAFMName', {}).get('afm') == text:
                                entries_found.append({
                                    'subject': d.get('subject'),
                                    'ada': d.get('ada'),
                                    'date': d.get('issueDate'),
                                    'amount': s.get('expenseAmount', {}).get('amount', '0')
                                })


                        for r in extra.get('donationReceiver', []):
                            if r.get('afm') == text:
                                entries_found.append({
                                    'subject': d.get('subject'),
                                    'ada': d.get('ada'),
                                    'date': d.get('issueDate'),
                                    'amount': extra.get('amountWithVAT', {}).get('amount', '0')
                                })

                    if entries_found:
                        response_text = f"### Αναλυτικές Εγγραφές για τον ΑΦΜ: `{text}`\n"
                        response_text += f"Βρέθηκαν συνολικά **{len(entries_found)}** εγγραφές:\n\n"
                        for entry in entries_found:
                            response_text += f"- **{entry['subject']}**\n"
                            response_text += f"  - Ημερ: {format_date(entry['date'])} | ΑΔΑ: `{entry['ada']}` | Ποσό: **{entry['amount']}€**\n"
                    else:
                        response_text = f"Δεν βρέθηκαν εγγραφές για τον ΑΦΜ `{text}` στην τρέχουσα ανάλυση."
                else:
                    response_text = "Πραγματοποιήστε πρώτα μια 'Συγκεντρωτική Ανάλυση (2)' για να μπορέσω να αναζητήσω το ΑΦΜ."
            #Αναζήτηση με ΑΔΑ
            elif is_ada(text):

                ada_encoded = quote(text)
                url = f"https://diavgeia.gov.gr/opendata/decisions/{ada_encoded}.json"
                try:
                    response = requests.get(url)
                    if response.ok:
                        act_data = response.json()
                        response_text = parse_diaugeia_act(act_data)
                        st.session_state.chat_step = "awaiting_org"
                    else:
                        response_text = "Δεν βρέθηκε απόφαση για τον ΑΔΑ που έδωσες."
                        st.session_state.chat_step = "awaiting_org"
                except:
                    response_text = "Σφάλμα κατά την ανάκτηση της απόφασης."
                    st.session_state.chat_step = "awaiting_org"

            # ΠΕΡΙΣΣΟΤΕΡΑ (Αποτελέσματα)
            elif text.lower() in ["περισσότερα", "περισσοτερα"] and st.session_state.selected_org_uid and st.session_state.chat_step == "results":

                next_page = st.session_state.current_page + 1
                uid = st.session_state.selected_org_uid

                decisions = fetch_decisions_by_uid(
                    uid,
                    from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                    to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                    page=next_page,
                    size=st.session_state.page_size,
                    decision_type_uid=st.session_state.selected_type_uid
                )

                if decisions:
                    st.session_state.current_decisions.extend(decisions)
                    st.session_state.current_page = next_page
                    start_idx = st.session_state.current_index
                    end_idx = start_idx + len(decisions)
                    st.session_state.current_index = end_idx

                    response_text = f"Εμφάνιση αποφάσεων {start_idx + 1} έως {end_idx} από {st.session_state.total_decisions}\n\n"
                    for dec in decisions:
                        response_text += f"- **{dec.get('subject', 'Χωρίς θέμα')}** ({format_date(dec.get('issueDate', 0))}) - ΑΔΑ: `{dec.get('ada', '-')}`\n"

                    if end_idx < st.session_state.total_decisions:
                        response_text += "\nΥπάρχουν περισσότερες αποφάσεις. Πληκτρολόγησε **'περισσότερα'**."
                else:
                    response_text = "Δεν υπάρχουν άλλες αποφάσεις να εμφανιστούν."

            #ΑΝΑΜΟΝΗ ΤΥΠΟΥ ΑΠΟΦΑΣΗΣ
            elif st.session_state.chat_step == "awaiting_type":
                match = next((dt for dt in decision_types if dt["uid"].upper() == text.upper()), None)

                if text.lower() == "όλοι":
                    st.session_state.selected_type_uid = None
                    st.session_state.selected_type_label = "Όλοι οι τύποι"
                    st.session_state.chat_step = "awaiting_dates"


                    max_date = st.session_state.from_date + relativedelta(months=+6)

                    response_text = (
                        f" Επιλέχθηκε: **Όλοι οι τύποι**.\n\n"
                        f" Ποια είναι η **ΑΡΧΙΚΗ** ημερομηνία (Από); \n"
                        f"*(Πρέπει η 'Έως' να είναι το πολύ 6 μήνες μετά την 'Από')*\n\n"
                        f" (Πληκτρολόγησε την ημερομηνία σε μορφή `ΗΗ/ΜΜ/ΕΕΕΕ`.)"
                    )
                elif match:
                    st.session_state.selected_type_uid = match["uid"]
                    st.session_state.selected_type_label = match["label"]
                    st.session_state.chat_step = "awaiting_dates"


                    max_date = st.session_state.from_date + relativedelta(months=+6)

                    response_text = (
                        f"Επιλέχθηκε τύπος: **{match['label']}** ({match['uid']}).\n\n"
                        f"Ποια είναι η **ΑΡΧΙΚΗ** ημερομηνία (Από); \n"
                        f"*(Πρέπει η 'Έως' να είναι το πολύ 6 μήνες μετά την 'Από')*\n\n"
                        f" (Πληκτρολόγησε την ημερομηνία σε μορφή `ΗΗ/ΜΜ/ΕΕΕΕ`.)"
                    )
                else:
                    response_text = "Άκυρος κωδικός. Δώσε τον κωδικό του τύπου από τη λίστα ή 'όλοι'."

            #ΑΝΑΜΟΝΗ ΗΜΕΡΟΜΗΝΙΩΝ (ΑΠΟ/ΕΩΣ) & ΕΛΕΓΧΟΣ 6 ΜΗΝΩΝ
            elif st.session_state.chat_step in ["awaiting_dates", "awaiting_to_date"]:

                new_step, step_response_text = get_user_input(st.session_state, text)

                st.session_state.chat_step = new_step
                response_text = step_response_text

                if st.session_state.chat_step == "dates_complete":


                    # ΕΙΔΙΚΟΥ ΤΥΠΟΥ (με δυνατότητα Ανάλυσης)
                    if st.session_state.selected_type_uid in ANALYSIS_TYPES:
                        st.session_state.chat_step = "awaiting_analysis_option"

                        org_label = fetch_organization_label(st.session_state.selected_org_uid)

                        response_text += (
                            f"\nΟλοκληρώθηκαν τα φίλτρα για **{st.session_state.selected_type_label}** του **{org_label}**.\n\n"
                            f"Τι θέλεις να δεις; \n"
                            f"- Πληκτρολόγησε **'1'** για **Λεπτομερή Λίστα**\n"
                            f"- Πληκτρολόγησε **'2'** για **Συγκεντρωτικά Στοιχεία**"
                        )

                    #ΓΕΝΙΚΟΥ ΤΥΠΟΥ (απευθείας Αποτελέσματα)
                    else:
                        st.session_state.chat_step = "results"
                        uid = st.session_state.selected_org_uid

                        decisions = fetch_decisions_by_uid(
                            uid,
                            from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                            to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                            page=0,
                            size=st.session_state.page_size,
                            decision_type_uid=st.session_state.selected_type_uid
                        )
                        total_decisions = fetch_decision_count(
                            uid,
                            from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                            to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                            decision_type_uid=st.session_state.selected_type_uid
                        )

                        st.session_state.total_decisions = total_decisions
                        st.session_state.current_decisions = decisions
                        st.session_state.current_index = len(decisions)
                        st.session_state.current_page = 0

                        selected_type_info = f" για τύπο: **{st.session_state.selected_type_label}**" if st.session_state.selected_type_uid else ""
                        org_label = fetch_organization_label(uid)

                        response_text += (
                            f"\n**Ολοκληρώθηκε η αναζήτηση** για τον οργανισμό **{org_label}** ({uid}){selected_type_info} "
                            f"μεταξύ {format_date(datetime.combine(st.session_state.from_date, datetime.min.time()))} και {format_date(datetime.combine(st.session_state.to_date, datetime.min.time()))}.\n\n"
                            f"Βρέθηκαν συνολικά **{total_decisions}** αποφάσεις. Εμφανίζονται οι 1 έως {len(decisions)}.\n\n"
                        )

                        if total_decisions > 0:
                            for dec in decisions:
                                response_text += f"- **{dec.get('subject', 'Χωρίς θέμα')}** ({format_date(dec.get('issueDate', 0))}) - ΑΔΑ: `{dec.get('ada', '-')}`\n"

                        if len(decisions) < total_decisions and total_decisions > 0:
                            response_text += "\nΥπάρχουν περισσότερες αποφάσεις. Πληκτρολόγησε **'περισσότερα'**."
                        elif total_decisions == 0:
                            response_text += "\nΔεν βρέθηκε καμία απόφαση με αυτά τα κριτήρια. Πληκτρολόγησε νέο οργανισμό."
                            st.session_state.chat_step = "awaiting_org"
                            st.session_state.selected_org_uid = None

            # ΕΠΙΛΟΓΗ ΕΙΔΟΥΣ ΑΝΑΛΥΣΗΣ ΓΙΑ ΕΙΔΙΚΟΥΣ ΤΥΠΟΥΣ
            elif st.session_state.chat_step == "awaiting_analysis_option":
                uid = st.session_state.selected_org_uid
                current_type_uid = st.session_state.selected_type_uid

                total_decisions = fetch_decision_count(
                    uid,
                    from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                    to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                    decision_type_uid=current_type_uid
                )

                if text.strip() == "1":
                    st.session_state.chat_step = "results"

                    decisions = fetch_decisions_by_uid(
                        uid,
                        from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                        to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                        page=0,
                        size=st.session_state.page_size,
                        decision_type_uid=current_type_uid
                    )

                    st.session_state.total_decisions = total_decisions
                    st.session_state.current_decisions = decisions
                    st.session_state.current_index = len(decisions)
                    st.session_state.current_page = 0

                    contract_text = "Πράξη" if total_decisions == 1 else "Πράξεις"
                    response_text = (
                        f"Επιλέχθηκε: **Λεπτομερής Λίστα {st.session_state.selected_type_label}**.\n"
                        f"Βρέθηκαν συνολικά **{total_decisions}** {contract_text}. Εμφανίζονται οι 1 έως {len(decisions)}.\n\n"
                    )

                    if total_decisions > 0:
                        for dec in decisions:
                            response_text += f"- **{dec.get('subject', 'Χωρίς θέμα')}** ({format_date(dec.get('issueDate', 0))}) - ΑΔΑ: `{dec.get('ada', '-')}`\n"

                    if len(decisions) < total_decisions and total_decisions > 0:
                        response_text += "\nΥπάρχουν περισσότερες αποφάσεις. Πληκτρολόγησε **'περισσότερα'**."
                    elif total_decisions == 0:
                        response_text += "\nΔεν βρέθηκε καμία πράξη με αυτά τα κριτήρια. Πληκτρολόγησε νέο οργανισμό."
                        st.session_state.chat_step = "awaiting_org"
                        st.session_state.selected_org_uid = None

                elif text.strip() == "2":
                    st.session_state.chat_step = "awaiting_org"
                    max_analysis_cap = 5000  # Ορισμός ορίου για την ανάλυση

                    decisions_for_analysis = fetch_all_decisions(
                        uid,
                        from_date=datetime.combine(st.session_state.from_date, datetime.min.time()),
                        to_date=datetime.combine(st.session_state.to_date, datetime.max.time()),
                        decision_type_uid=current_type_uid,
                        max_decisions=max_analysis_cap
                    )
                    #ΑΠΟΘΗΚΕΥΣΗ ΓΙΑ ΜΕΛΛΟΝΤΙΚΟ ΦΙΛΤΡΑΡΙΣΜΑ
                    st.session_state.last_analysis_decisions = decisions_for_analysis


                    if current_type_uid == "Δ.1":
                        contract_text = "Πράξη" if total_decisions == 1 else "Πράξεις"
                        response_text = f"### Συγκεντρωτικά Στοιχεία (Δ.1) | Σύνολο: {total_decisions} {contract_text}\n\n"
                        if decisions_for_analysis:
                            response_text += analyze_decisions_router(decisions_for_analysis, current_type_uid)
                    else:
                        response_text = analyze_decisions_router(decisions_for_analysis, current_type_uid)

                    if not decisions_for_analysis and total_decisions > 0:
                        response_text += "\nΔεν ήταν δυνατή η ανάλυση των αποφάσεων."
                    elif total_decisions == 0:
                        response_text = "Δεν βρέθηκε καμία πράξη για ανάλυση."

                    if total_decisions > max_analysis_cap and decisions_for_analysis:
                        response_text += f"\n\n**Προσοχή:** Η ανάλυση έγινε με βάση τις **πρώτες {max_analysis_cap}** πράξεις. Για μεγαλύτερη ακρίβεια θα πρέπει να χρησιμοποιηθούν μικρότερο εύρος ημερομηνιών."

                    response_text += "\n\nΠληκτρολόγησε νέο οργανισμό, uid ή ΑΔΑ για να συνεχίσεις."
                    st.session_state.selected_org_uid = None

                else:
                    response_text = "Άκυρη επιλογή. Πληκτρολόγησε **'1'** για Λίστα ή **'2'** για Ανάλυση."

            # ΕΠΙΛΟΓΗ ΟΡΓΑΝΙΣΜΟΥ (Αναζήτηση με UID ή Όνομα)
            elif st.session_state.chat_step == "awaiting_org" or is_uid(text, organizations):
                uid_to_search = None

                if is_uid(text, organizations):
                    uid_to_search = text
                else:
                    matches = search_organizations(text, organizations)
                    if not matches:
                        response_text = "Δεν βρέθηκε κάποιος σχετικός οργανισμός. Δώσε άλλο όνομα ή το uid."
                        st.session_state.chat_step = "awaiting_org"
                    elif len(matches) == 1:
                        uid_to_search = matches[0]['uid']
                    else:
                        contract_text1 = "Βρέθηκε" if len(matches) == 1 else "Βρέθηκαν"
                        contract_text2 = "σχετικός οργανισμός" if len(matches) == 1 else "σχετικοί οργανισμοί"
                        response_text = f"{contract_text1} {len(matches)} {contract_text2}:\n\n"
                        for org in matches:
                            response_text += f"- **{org['label']}** (uid: `{org['uid']}`)\n"
                        response_text += "\nΑν θέλεις να δεις αποφάσεις, πληκτρολόγησε το **uid** του οργανισμού."
                        st.session_state.chat_step = "awaiting_org"

                if uid_to_search:
                    st.session_state.selected_org_uid = uid_to_search
                    st.session_state.chat_step = "awaiting_type"

                    # ΝΕΑ ΛΟΓΙΚΗ: Διαχωρισμός τύπων
                    analysis_types_list = [dt for dt in decision_types if dt["uid"] in ANALYSIS_TYPES]
                    other_types_list = [dt for dt in decision_types if dt["uid"] not in ANALYSIS_TYPES]

                    type_options = "### 📑 Τύποι με δυνατότητα Λίστας\n"
                    type_options += "\n".join([f"- **{dt['uid']}**: {dt['label']}" for dt in other_types_list])

                    type_options += "\n\n### 📈 Τύποι με *Συγκεντρωτικά Στοιχεία*\n"
                    type_options += "\n".join([f"- **{dt['uid']}**: {dt['label']}" for dt in analysis_types_list])

                    response_text = (
                        f"Επιλέχθηκε οργανισμός: **{fetch_organization_label(uid_to_search)}** ({uid_to_search}).\n\n"
                        f"Ποιο **είδος** σε ενδιαφέρει; (Πληκτρολόγησε τον **κωδικό** ή **'όλοι'**)\n\n"
                        f"{type_options}"
                    )

            #Άγνωστη Εντολή
            else:
                response_text = "Δεν κατάλαβα την εντολή σου. Δοκίμασε να δώσεις όνομα οργανισμού, uid ή ΑΔΑ."
                st.session_state.chat_step = "awaiting_org"

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})