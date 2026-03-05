import unicodedata
from greek_stemmer import stemmer
from datetime import datetime
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

def normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    text = text.replace(',', '')
    return text


def stem_tokens(text):
    tokens = normalize(text).split()
    return set([stemmer.stem_word(word, 'VBG').lower() for word in tokens])


def is_uid(text, organizations):
    return text.strip() in [org["uid"] for org in organizations]


def is_ada(text):
    text = text.strip()
    # Έλεγχος αν μοιάζει με ΑΔΑ: περιέχει παύλα και έχει ικανοποιητικό μήκος
    return "-" in text and len(text) >= 9


def format_date(ms):
    try:
        if isinstance(ms, (int, float)):
            return datetime.fromtimestamp(ms / 1000).strftime("%d/%m/%Y")
        elif isinstance(ms, datetime):
            return ms.strftime("%d/%m/%Y")
        return "Άγνωστη ημερομηνία"
    except:
        return "Άγνωστη ημερομηνία"


def fetch_dates_from_user(from_date_str, to_date_str, from_date_default, to_date_default):
    """
    Διαβάζει τις ημερομηνίες από strings, τις επαληθεύει και ελέγχει
    αν η διαφορά τους είναι έως 6 μήνες. Επιστρέφει τις ημερομηνίες (datetime.date)
    ή raises ValueError.
    """

    if from_date_str:
        from_date = date_parser.parse(from_date_str, dayfirst=True).date()
    else:
        from_date = from_date_default

    if to_date_str:
        to_date = date_parser.parse(to_date_str, dayfirst=True).date()
    else:
        to_date = to_date_default

    if from_date > to_date:
        raise ValueError("Η ημερομηνία 'Από' πρέπει να είναι πριν την 'Έως'.")

    max_to_date = from_date + relativedelta(months=+6)

    if to_date > max_to_date:

        raise ValueError(
            f"Το διάστημα υπερβαίνει τους 6 μήνες. Η μέγιστη αποδεκτή ημερομηνία 'Έως' για την επιλεγμένη 'Από' είναι η **{format_date(datetime.combine(max_to_date, datetime.min.time()))}**."
        )

    return from_date, to_date
def format_extra_fields(extra_fields):
    """
    Επεξεργάζεται ένα λεξικό extraFieldValues και μορφοποιεί τα πεδία
    για εμφάνιση. Χειρίζεται απλές τιμές και προσπαθεί να εμφανίσει
    λογικά τις σύνθετες δομές (λίστες / λεξικά).
    """
    results = []


    skip_fields = [
        "person", "awardAmount", "donationGiver", "donationReceiver",
        "amountWithVAT", "grantor", "grantee", "sponsor", "expenseAmount",
        "sponsorAFMName", "fek"  # Παραδείγματα σύνθετων πεδίων
    ]


    # 1. Ποσό Ανάθεσης/Δαπάνης
    if "awardAmount" in extra_fields and extra_fields["awardAmount"].get("amount"):
        award = extra_fields["awardAmount"]
        results.append(f"** Ποσό Ανάθεσης/Δαπάνης:** **{award.get('amount', '–')} {award.get('currency', '')}**")

    # 2. Ποσό Δωρεάς/Επιχορήγησης
    if "amountWithVAT" in extra_fields and extra_fields["amountWithVAT"].get("amount"):
        amount_vat = extra_fields["amountWithVAT"]
        results.append(
            f"** Ποσό Δωρεάς/Επιχορήγησης:** **{amount_vat.get('amount', '–')} {amount_vat.get('currency', '')}**")

    # 3. Ανάδοχοι (για Δ.1)
    if extra_fields.get("person"):
        for i, person in enumerate(extra_fields["person"]):
            results.append(f"- **Ανάδοχος {i + 1}:** {person.get('name', '–')} (ΑΦΜ: {person.get('afm', '–')})")

    # 4. Χορηγοί / Δικαιούχοι (για Β.2.1/Β.2.2)
    if extra_fields.get("sponsor"):
        results.append(f"###  Στοιχεία Δαπανών")
        for i, s in enumerate(extra_fields["sponsor"], 1):
            afm_info = s.get("sponsorAFMName", {})
            exp_amount = s.get("expenseAmount", {})
            sponsor_line = (
                f"- **Δικαιούχος/Χορηγός:** {afm_info.get('name', 'Άγνωστος')} (ΑΦΜ: {afm_info.get('afm', '-')}) | "
                f"Ποσό: **{exp_amount.get('amount', '-')} {exp_amount.get('currency', '')}** "
            )
            results.append(sponsor_line)

    if results and not results[-1].startswith("\n###  Λοιπά Πρόσθετα Πεδία"):
        results.append("\n###  Λοιπά Πρόσθετα Πεδία")

    for key, value in extra_fields.items():
        if key not in skip_fields and value and not isinstance(value, (dict, list)):
            display_key = key.replace('Type', ' Τύπος').replace('Id', ' ID').replace('Date', ' Ημερομηνία').replace(
                'Url', ' URL')

            results.append(f"**{display_key.replace('_', ' ').strip().capitalize()}:** {value}")

    return results