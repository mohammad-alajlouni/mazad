"""The terms of entry to the auction (guide p.19), set as text.

Each kind of auction has its own terms (in-person, electronic, hybrid), written
in for every auction of that kind; they may be changed for one
(some terms differ between auctions: the commission, VAT...). They keep the
guide's page: the title, the frame and the bar beneath (booklet-art), each
term a justified paragraph after its square bullet, in Ruaq Light 11.57 on
14.04 pt lines. Longer terms are set a little smaller, all of them always on
the one page; terms too long for it even at TERMS_MIN are reported.
"""

from .composer import justified, wrap_lines

# The terms of each kind of auction, one to a paragraph, as the notes give
# them (in-person, electronic, and hybrid: electronic and in-person).
PAY_ON_AWARD = (
    "عند رسو المزاد على المشتري، يتم سداد المبلغ شاملًا قيمة السعي فورًا، "
    "وفي حال تعذر السداد خلال ثلاثة أيام عمل من تاريخ صدور محضر الترسية "
    "فيعاد البيع على حساب المشتري المتخلف عن السداد، ويتحمل المشتري المتخلف "
    "تكاليف إعادة البيع على حسابه وللمركز الحق في تمديد الفترة من ثلاثة أيام "
    "إلى عشرة أيام إذا دعت الحاجة."
)
COMMON = (
    "المعاينة للأصل خلال فترة الإعلان.",
    "يسقط خيار المجلس حال رسو المزاد.",
    (
        "يلتزم من يرسو عليه المزاد بسداد مبلغ السعي 2.5 % من ثمن البيع "
        "شاملًا لضريبة القيمة المضافة."
    ),
    (
        "يلتزم المشتري بسداد ضريبة التصرفات العقارية بقيمة 5 % من ثمن البيع "
        "وذلك خلال فترة التحصيل المحددة أعلاه."
    ),
    (
        "تم الإعلان بناءً على البيانات والمواصفات الواردة في وثيقة العقار ولا "
        "يتحمل المركز أدنى مسؤولية عن أي اختلاف في العقار على أرض الواقع عما "
        "هو مدون في الوثيقة."
    ),
    "يتم البيع والإفراغ وفقًا لقواعد مركز الإسناد والتصفية «إنفاذ».",
)
GUIDE_TERMS = {
    "physical": (
        (
            "سداد مبلغ المشاركة بالقيمة المحددة لكل أصل عن طريق فاتورة سداد "
            "صادرة من مركز الإسناد والتصفية، ويعتبر المبلغ جزءًا من الثمن لمن "
            "يرسو عليه المزاد ولا يحق له استرداده، وفي حالة رسو المزاد يتم سداد "
            "بقية المبلغ فور صدور فاتورة السداد وذلك خلال مدة التحصيل المعتمدة."
        ),
        (
            "حضور المشارك أو وكيله الشرعي لصالة المزاد، وعند رسو المزاد على "
            "المشتري، يتم سداد المبلغ شاملًا قيمة السعي فورًا، وفي حال تعذر "
            "السداد خلال ثلاثة أيام عمل من تاريخ صدور محضر الترسية فيعاد البيع "
            "على حساب المشتري المتخلف عن السداد، ويتحمل المشتري المتخلف تكاليف "
            "إعادة البيع على حسابه وللمركز الحق في تمديد الفترة من ثلاثة أيام "
            "إلى عشرة أيام إذا دعت الحاجة."
        ),
        *COMMON,
    ),
    "electronic": (
        "التسجيل في منصة المزاد الإلكتروني.",
        (
            "سداد مبلغ المشاركة بالقيمة المحددة لكل أصل عن طريق منصة المزاد "
            "الإلكتروني ويعتبر المبلغ جزءًا من الثمن لمن يرسو عليه المزاد ولا "
            "يحق له استرداده، وفي حالة رسو المزاد يتم سداد بقية المبلغ فور صدور "
            "فاتورة السداد وذلك خلال مدة التحصيل المعتمدة."
        ),
        PAY_ON_AWARD,
        *COMMON,
    ),
    "hybrid": (
        (
            "من يرغب في المزايدة الإلكترونية عليه التسجيل في منصة المزاد "
            "الإلكتروني، وسداد مبلغ المشاركة بالقيمة المحددة لكل أصل عن طريق "
            "منصة المزاد الإلكتروني، ويعتبر المبلغ جزءًا من الثمن لمن يرسو عليه "
            "المزاد ولا يحق له استرداده، وفي حالة رسو المزاد يتم سداد بقية "
            "المبلغ فور صدور فاتورة السداد وذلك خلال مدة التحصيل المعتمدة."
        ),
        (
            "من يرغب في المزايدة حضوريًا عليه تقديم شيك مصدّق باسم مركز الإسناد "
            "والتصفية بالقيمة المحددة لكل أصل، ويعتبر المبلغ جزءًا من الثمن لمن "
            "يرسو عليه المزاد ولا يحق له استرداده، وفي حالة رسو المزاد يتم سداد "
            "بقية المبلغ فور صدور فاتورة السداد وذلك خلال مدة التحصيل المعتمدة."
        ),
        "من يرغب في المزايدة حضوريًا عليه الحضور بنفسه أو حضور وكيله الشرعي لقاعة المزاد.",
        PAY_ON_AWARD,
        *COMMON,
    ),
}
GUIDE_TEXTS = {kind: "\n".join(terms) for kind, terms in GUIDE_TERMS.items()}
# The hybrid auction's (every kind's terms but its own first ones).
TERMS = GUIDE_TEXTS["hybrid"]


def guide_terms(kind):
    """The guide's terms for a kind of auction (physical, electronic, hybrid)."""
    return GUIDE_TEXTS.get(kind or "hybrid", TERMS)


FONT = "RuaqArabic-Light"
SIZE, LINE, GAP = 11.57, 14.04, 8.8  # the guide's size, line pitch, paragraph gap
TERMS_MIN = 8.0
RIGHT, WIDTH = 442.65, 287.5  # the text's right edge and width
FIRST, LAST = 181.0, 636.0  # first baseline; the last may reach (above the bar)
BULLET = (455.16, 4.54)  # the square's left edge and side
BULLET_RISE = 4.1  # from a paragraph's first baseline up to its bullet's centre


def terms_of(auction):
    """The auction's own terms, or the guide's for its kind."""
    text = str((auction or {}).get("terms_text") or "").replace("\r\n", "\n").strip()
    return text or guide_terms((auction or {}).get("auction_type"))


def paragraphs(text):
    return [p.strip() for p in text.split("\n") if p.strip()]


def height(text, size):
    """From the first baseline to the last, at a size."""
    lines = sum(len(wrap_lines(p, size, WIDTH * 0.98, FONT)) for p in paragraphs(text))
    count = len(paragraphs(text))
    scale = size / SIZE
    return (lines - 1) * LINE * scale + (count - 1) * GAP * scale


def terms_size(text):
    """The largest size up to the guide's that sets the terms on their page;
    (TERMS_MIN, False) when even that is too large."""
    size = SIZE
    while FIRST + height(text, size) > LAST:
        if size <= TERMS_MIN:
            return TERMS_MIN, False
        size = max(TERMS_MIN, round(size - 0.25, 2))
    return size, True


def terms_page(auction):
    text = terms_of(auction)
    size, _ = terms_size(text)
    scale = size / SIZE
    line, gap = round(LINE * scale, 2), GAP * scale
    rows, base = [], FIRST
    for paragraph in paragraphs(text):
        lines = justified(paragraph, size, WIDTH, FONT)
        rows.append(
            {
                "bullet": round(base - BULLET_RISE * scale, 2),
                "lines": [
                    {**x, "base": round(base + i * line, 2)}
                    for i, x in enumerate(lines)
                ],
            }
        )
        base += len(lines) * line + gap
    return {
        "kind": "terms",
        "auction_type": (auction or {}).get("auction_type"),
        "size": size,
        "terms": rows,
    }


def longest(text):
    """How many characters of the terms fit at the smallest size."""
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if FIRST + height(text[:middle], TERMS_MIN) <= LAST:
            low = middle
        else:
            high = middle - 1
    return low
