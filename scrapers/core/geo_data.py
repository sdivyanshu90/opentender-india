"""Curated geography tables for deterministic state/district tagging (see geo.py).

Sources: state/UT list and districts from the Census of India / LGD (Local Government Directory,
lgdirectory.gov.in) as known publicly; pincode circles from the India Post PIN code scheme
(first digit = zone, first two digits = sub-zone/postal circle). The district lists are curated,
not exhaustive; names that exist in more than one state live in AMBIGUOUS_PLACES and are only
ever used as a consistency hint, never as the sole evidence.
"""

from __future__ import annotations

# canonical state/UT name -> names that indicate it (lowercase, whole-word matched)
STATE_NAMES: dict[str, list[str]] = {
    "Andhra Pradesh": ["andhra pradesh", "andhrapradesh", "andhra"],
    "Arunachal Pradesh": ["arunachal pradesh", "arunachal"],
    "Assam": ["assam"],
    "Bihar": ["bihar"],
    "Chhattisgarh": ["chhattisgarh", "chattisgarh", "chhatisgarh"],
    "Goa": ["goa"],
    "Gujarat": ["gujarat"],
    "Haryana": ["haryana"],
    "Himachal Pradesh": ["himachal pradesh", "himachal"],
    "Jharkhand": ["jharkhand"],
    "Karnataka": ["karnataka"],
    "Kerala": ["kerala", "keralam"],
    "Madhya Pradesh": ["madhya pradesh", "madhyapradesh"],
    "Maharashtra": ["maharashtra"],
    "Manipur": ["manipur"],
    "Meghalaya": ["meghalaya"],
    "Mizoram": ["mizoram"],
    "Nagaland": ["nagaland"],
    "Odisha": ["odisha", "orissa"],
    "Punjab": ["punjab"],
    "Rajasthan": ["rajasthan"],
    "Sikkim": ["sikkim"],
    "Tamil Nadu": ["tamil nadu", "tamilnadu"],
    "Telangana": ["telangana"],
    "Tripura": ["tripura"],
    "Uttar Pradesh": ["uttar pradesh", "uttarpradesh"],
    "Uttarakhand": ["uttarakhand", "uttaranchal"],
    "West Bengal": ["west bengal", "westbengal"],
    "Andaman and Nicobar Islands": ["andaman and nicobar", "andaman", "nicobar"],
    "Chandigarh": ["chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["dadra and nagar haveli", "daman and diu", "daman", "silvassa"],
    "Delhi": ["nct of delhi", "nct delhi", "delhi ncr"],
    "Jammu and Kashmir": ["jammu and kashmir", "jammu kashmir", "kashmir"],
    "Ladakh": ["ladakh"],
    "Lakshadweep": ["lakshadweep"],
    "Puducherry": ["puducherry", "pondicherry"],
}

# Places (districts, major cities) -> state. Lowercase, whole-word matched.
PLACES: dict[str, list[str]] = {
    "Maharashtra": [
        "mumbai", "mumbai suburban", "navi mumbai", "bombay", "pune", "poona", "nagpur", "nashik", "nasik", "thane",
        "dombivli", "solapur", "kolhapur", "amravati", "akola", "latur", "nanded", "jalgaon", "satara", "sangli",
        "ratnagiri", "raigad", "palghar", "chandrapur", "wardha", "yavatmal", "gondia", "bhandara", "gadchiroli",
        "washim", "buldhana", "hingoli", "parbhani", "jalna", "beed", "dhule", "nandurbar", "sindhudurg",
        "chhatrapati sambhajinagar", "sambhajinagar", "osmanabad", "dharashiv", "ahmednagar", "ahmadnagar",
        "ahilyanagar", "pimpri chinchwad", "pimpri", "panvel", "vasai", "virar", "bhiwandi", "ulhasnagar",
        "malegaon", "karad", "pandharpur", "lonavala", "lonavla", "shirdi", "mira bhayandar", "khopoli", "alibag",
        "chiplun", "nhava sheva", "trombay", "tarapur", "bhusawal", "ichalkaranji", "kamptee", "deolali",
        "dehu road", "khadakwasla", "mulund", "bandra", "andheri", "worli", "colaba", "chembur", "kurla", "powai",
        "ambernath", "badlapur", "talegaon", "baramati", "wai", "miraj", "kudal", "sawantwadi", "gondiya",
    ],
    "Gujarat": [
        "ahmedabad", "gandhinagar", "surat", "vadodara", "rajkot", "bhavnagar", "jamnagar", "junagadh", "kutch",
        "kachchh", "bhuj", "bharuch", "valsad", "navsari", "mehsana", "morbi", "porbandar", "amreli", "dahod",
        "godhra", "palanpur", "himmatnagar", "vapi", "ankleshwar", "kandla", "mundra", "dahej", "surendranagar",
        "gir somnath", "dwarka", "botad", "anand", "nadiad", "kheda", "sabarkantha", "banaskantha", "tapi",
    ],
    "Goa": ["panaji", "panjim", "margao", "vasco da gama", "mormugao", "ponda", "mapusa", "south goa", "north goa"],
    "Karnataka": [
        "bengaluru", "bangalore", "mysuru", "mysore", "hubli", "hubballi", "dharwad", "belagavi", "belgaum",
        "mangaluru", "mangalore", "kalaburagi", "gulbarga", "ballari", "bellary", "shivamogga", "shimoga",
        "tumakuru", "tumkur", "davanagere", "hassan", "mandya", "udupi", "raichur", "koppal", "gadag", "haveri",
        "chitradurga", "kolar", "chikkamagaluru", "chikmagalur", "kodagu", "coorg", "bagalkot", "vijayapura",
        "yadgir", "chamarajanagar", "ramanagara", "chikkaballapur", "uttara kannada", "dakshina kannada", "karwar",
        "bidar", "kolar gold fields",
    ],
    "Kerala": [
        "thiruvananthapuram", "trivandrum", "kollam", "pathanamthitta", "alappuzha", "alleppey", "kottayam",
        "idukki", "ernakulam", "kochi", "cochin", "thrissur", "trichur", "palakkad", "palghat", "malappuram",
        "kozhikode", "calicut", "wayanad", "kannur", "cannanore", "kasaragod", "kasargod", "kakkanad", "aluva",
        "angamaly", "chavara", "thodupuzha", "muvattupuzha", "chalakudy", "thalassery", "vizhinjam", "kayamkulam",
    ],
    "Tamil Nadu": [
        "chennai", "madras", "coimbatore", "madurai", "tiruchirappalli", "trichy", "tirunelveli", "salem", "erode",
        "tiruppur", "vellore", "thanjavur", "tanjore", "thoothukudi", "tuticorin", "kanyakumari", "kancheepuram",
        "kanchipuram", "chengalpattu", "tiruvallur", "cuddalore", "dindigul", "karur", "namakkal", "krishnagiri",
        "dharmapuri", "nagapattinam", "tiruvarur", "pudukkottai", "ramanathapuram", "sivaganga", "virudhunagar",
        "theni", "nilgiris", "ooty", "perambalur", "ariyalur", "tenkasi", "ranipet", "tirupathur", "avadi",
        "ennore", "hosur", "villupuram", "kallakurichi", "mayiladuthurai", "tiruvannamalai",
    ],
    "Telangana": [
        "hyderabad", "secunderabad", "warangal", "hanamkonda", "karimnagar", "nizamabad", "khammam", "nalgonda",
        "mahabubnagar", "mahbubnagar", "adilabad", "medak", "sangareddy", "rangareddy", "ranga reddy", "siddipet",
        "suryapet", "jagtial", "peddapalli", "kamareddy", "medchal", "vikarabad", "nagarkurnool", "wanaparthy",
        "jogulamba gadwal", "mancherial", "nirmal", "bhadradri kothagudem", "kothagudem", "ramagundam",
        "mulugu", "jangaon", "mahabubabad", "yadadri bhuvanagiri", "bhongir", "ghmc",
    ],
    "Andhra Pradesh": [
        "visakhapatnam", "vizag", "vijayawada", "guntur", "nellore", "kurnool", "tirupati", "kadapa", "cuddapah",
        "anantapur", "anantapuramu", "chittoor", "srikakulam", "vizianagaram", "kakinada", "rajahmundry",
        "rajamahendravaram", "eluru", "ongole", "prakasam", "amaravati", "machilipatnam", "krishna district",
        "west godavari", "east godavari", "nandyal", "bapatla", "palnadu", "annamayya", "sri sathya sai",
        "parvathipuram", "anakapalli", "narasaraopet", "tadepalligudem", "hindupur", "dharmavaram", "proddatur",
    ],
    "Odisha": [
        "bhubaneswar", "cuttack", "puri", "rourkela", "sambalpur", "berhampur", "balasore", "baleshwar", "koraput",
        "jharsuguda", "angul", "dhenkanal", "keonjhar", "kendujhar", "mayurbhanj", "sundargarh", "bargarh",
        "bolangir", "balangir", "kalahandi", "rayagada", "jajpur", "kendrapara", "jagatsinghpur", "khordha",
        "nayagarh", "gajapati", "ganjam", "malkangiri", "nabarangpur", "nuapada", "boudh", "deogarh", "paradip",
        "talcher", "bhadrak", "subarnapur", "phulbani", "kandhamal",
    ],
    "West Bengal": [
        "kolkata", "calcutta", "howrah", "hooghly", "durgapur", "asansol", "siliguri", "darjeeling", "jalpaiguri",
        "cooch behar", "coochbehar", "malda", "murshidabad", "nadia", "kalyani", "barrackpore", "bardhaman",
        "burdwan", "purulia", "bankura", "birbhum", "medinipur", "midnapore", "haldia", "kharagpur", "alipurduar",
        "north 24 parganas", "south 24 parganas", "paschim medinipur", "purba medinipur", "dinajpur", "kalimpong",
        "bidhannagar", "salt lake", "garden reach", "dankuni", "tamluk",
    ],
    "Bihar": [
        "patna", "gaya", "bhagalpur", "muzaffarpur", "darbhanga", "purnia", "purnea", "begusarai", "arrah", "bhojpur",
        "nalanda", "bihar sharif", "samastipur", "sitamarhi", "madhubani", "saharsa", "supaul", "araria",
        "kishanganj", "katihar", "khagaria", "munger", "monghyr", "lakhisarai", "sheikhpura", "nawada", "jehanabad",
        "buxar", "kaimur", "rohtas", "sasaram", "siwan", "gopalganj", "saran", "chapra", "vaishali", "hajipur",
        "motihari", "bettiah", "jamui", "banka", "madhepura", "sheohar", "arwal", "barauni", "danapur",
    ],
    "Jharkhand": [
        "ranchi", "jamshedpur", "dhanbad", "bokaro", "deoghar", "hazaribagh", "giridih", "dumka", "palamu",
        "daltonganj", "chaibasa", "singhbhum", "gumla", "lohardaga", "latehar", "garhwa", "chatra", "koderma",
        "ramgarh", "pakur", "sahibganj", "godda", "jamtara", "simdega", "khunti", "seraikela", "kharsawan",
        "saraikela", "sindri",
    ],
    "Uttar Pradesh": [
        "lucknow", "kanpur", "varanasi", "banaras", "agra", "meerut", "ghaziabad", "noida", "greater noida",
        "prayagraj", "allahabad", "bareilly", "aligarh", "moradabad", "gorakhpur", "jhansi", "saharanpur",
        "mathura", "firozabad", "muzaffarnagar", "faizabad", "ayodhya", "azamgarh", "mirzapur", "sultanpur",
        "unnao", "rae bareli", "raebareli", "sitapur", "hardoi", "etawah", "kannauj", "farrukhabad", "mainpuri",
        "budaun", "badaun", "bijnor", "shahjahanpur", "pilibhit", "lakhimpur kheri", "bahraich", "gonda",
        "basti", "deoria", "ballia", "ghazipur", "jaunpur", "chandauli", "sonbhadra", "obra", "renukoot",
        "lalitpur", "mahoba", "chitrakoot", "banda", "fatehpur", "kaushambi", "amethi", "bulandshahr", "hapur",
        "baghpat", "shamli", "amroha", "sambhal", "rampur", "kushinagar", "maharajganj", "siddharthnagar",
        "ambedkar nagar", "barabanki", "hathras", "kasganj", "etah", "auraiya", "orai", "jalaun", "mau",
        "mughalsarai", "naini", "sahibabad", "gautam buddha nagar", "yamuna expressway",
    ],
    "Uttarakhand": [
        "dehradun", "haridwar", "rishikesh", "nainital", "haldwani", "almora", "pithoragarh", "pauri", "tehri",
        "chamoli", "rudraprayag", "uttarkashi", "bageshwar", "champawat", "udham singh nagar", "rudrapur", "kashipur",
        "roorkee", "mussoorie", "kotdwar",
    ],
    "Himachal Pradesh": [
        "shimla", "solan", "kangra", "dharamshala", "dharamsala", "kullu", "manali", "chamba", "sirmaur", "sirmour",
        "una", "kinnaur", "lahaul", "spiti", "palampur", "nahan", "baddi", "parwanoo", "paonta sahib",
    ],
    "Punjab": [
        "ludhiana", "amritsar", "jalandhar", "patiala", "bathinda", "mohali", "sas nagar", "pathankot", "hoshiarpur",
        "gurdaspur", "ferozepur", "firozpur", "fazilka", "faridkot", "muktsar", "moga", "sangrur", "barnala",
        "mansa", "kapurthala", "nawanshahr", "rupnagar", "ropar", "fatehgarh sahib", "tarn taran", "malerkotla",
        "khanna", "rajpura", "zirakpur", "abohar",
    ],
    "Haryana": [
        "gurugram", "gurgaon", "faridabad", "panipat", "ambala", "yamunanagar", "rohtak", "hisar", "karnal",
        "sonipat", "sonepat", "panchkula", "bhiwani", "sirsa", "jhajjar", "jind", "kaithal", "kurukshetra",
        "fatehabad", "rewari", "mahendragarh", "narnaul", "nuh", "mewat", "palwal", "charkhi dadri", "manesar",
        "bahadurgarh",
    ],
    "Rajasthan": [
        "jaipur", "jodhpur", "udaipur", "kota", "bikaner", "ajmer", "alwar", "bharatpur", "sikar", "jhunjhunu",
        "churu", "sri ganganagar", "sriganganagar", "hanumangarh", "nagaur", "pali", "barmer", "jaisalmer",
        "jalore", "sirohi", "bhilwara", "chittorgarh", "chittaurgarh", "rajsamand", "dungarpur", "banswara",
        "tonk", "sawai madhopur", "dausa", "karauli", "dholpur", "bundi", "baran", "jhalawar", "pratapgarh rajasthan",
        "khetri", "neemrana", "beawar", "kishangarh", "bhiwadi",
    ],
    "Madhya Pradesh": [
        "bhopal", "indore", "jabalpur", "gwalior", "ujjain", "sagar", "rewa", "satna", "ratlam", "dewas", "khandwa",
        "khargone", "burhanpur", "chhindwara", "betul", "hoshangabad", "narmadapuram", "vidisha", "sehore", "raisen",
        "guna", "shivpuri", "datia", "morena", "bhind", "sheopur", "tikamgarh", "chhatarpur", "panna", "damoh",
        "katni", "mandla", "dindori", "balaghat", "seoni", "narsinghpur", "shahdol", "umaria", "anuppur", "singrauli",
        "sidhi", "mandsaur", "neemuch", "shajapur", "rajgarh", "agar malwa", "dhar", "jhabua", "alirajpur",
        "barwani", "ashoknagar", "pithampur", "mhow", "nagda", "pachmarhi", "itarsi", "sarni", "waidhan",
    ],
    "Chhattisgarh": [
        "raipur", "bilaspur chhattisgarh", "durg", "bhilai", "korba", "raigarh", "rajnandgaon", "jagdalpur", "bastar",
        "dantewada", "kanker", "dhamtari", "mahasamund", "janjgir", "champa", "jashpur", "surguja", "ambikapur",
        "kawardha", "kabirdham", "narayanpur", "kondagaon", "sukma", "balod", "bemetara", "mungeli", "gariaband",
        "baloda bazar", "naya raipur", "korea chhattisgarh", "kurud",
    ],
    "Assam": [
        "guwahati", "dibrugarh", "silchar", "jorhat", "tezpur", "nagaon", "tinsukia", "sivasagar", "golaghat",
        "lakhimpur assam", "dhemaji", "karimganj", "sribhumi", "hailakandi", "cachar", "kamrup", "nalbari", "barpeta",
        "bongaigaon", "kokrajhar", "dhubri", "goalpara", "darrang", "sonitpur", "morigaon", "karbi anglong",
        "dima hasao", "duliajan", "digboi", "numaligarh", "namrup", "bokakhat",
    ],
    "Arunachal Pradesh": ["itanagar", "tawang", "pasighat", "naharlagun", "ziro", "bomdila", "along", "roing", "tezu"],
    "Manipur": ["imphal", "churachandpur", "thoubal", "bishnupur manipur", "ukhrul", "senapati", "tamenglong"],
    "Meghalaya": ["shillong", "tura", "jowai", "nongpoh", "williamnagar", "east khasi hills", "west garo hills"],
    "Mizoram": ["aizawl", "lunglei", "champhai", "serchhip", "kolasib", "mamit", "saiha"],
    "Nagaland": ["kohima", "dimapur", "mokokchung", "tuensang", "wokha", "zunheboto", "mon nagaland", "phek"],
    "Tripura": ["agartala", "dharmanagar", "udaipur tripura", "kailashahar", "ambassa", "belonia"],
    "Sikkim": ["gangtok", "namchi", "gyalshing", "mangan", "pelling", "rangpo"],
    "Jammu and Kashmir": [
        "srinagar", "jammu", "anantnag", "baramulla", "budgam", "pulwama", "kupwara", "bandipora", "ganderbal",
        "shopian", "kulgam", "kathua", "udhampur", "doda", "kishtwar", "ramban", "reasi", "poonch", "rajouri",
        "samba",
    ],
    "Ladakh": ["leh", "kargil"],
    "Delhi": ["new delhi", "delhi"],
    "Chandigarh": [],
    "Puducherry": ["karaikal", "yanam", "mahe puducherry"],
    "Lakshadweep": ["kavaratti", "agatti", "minicoy"],
    "Andaman and Nicobar Islands": ["port blair", "sri vijaya puram", "car nicobar"],
    "Dadra and Nagar Haveli and Daman and Diu": ["nagar haveli"],
}

# Names that are also given names, common words, or surnames. They only count when another,
# independent signal (pincode, explicit state name, or a strong place) points to the same state.
WEAK_PLACES: set[str] = {
    "ramgarh", "raipur",
    "kalyan", "delhi", "new delhi", "sagar", "dhar", "anand", "mau", "banda", "wai", "pali", "una", "along",
    "tura", "mon nagaland", "samba", "mangan", "vasai", "puri", "salt lake", "tapi", "kolar gold fields",
    "mandla", "reasi", "rampur", "baddi", "kota", "champa", "tiruvallur", "pimpri", "agar malwa", "rajgarh",
    "udaipur tripura", "pratapgarh rajasthan", "bilaspur chhattisgarh", "lakhimpur assam", "bishnupur manipur",
    "mahe puducherry", "krishna district", "leh", "hassan", "sidhi", "banka", "arwal", "baran", "nuh", "basti", "mansa", "guna", "moga", "gonda",
}

# Real district/city names that are also frequent village, ward or road names elsewhere (found by testing
# against state-portal data). They only count when at least two different fields (e.g. title and
# authority chain) point to the same state.
VILLAGE_PRONE: set[str] = {
    "sultanpur", "rajpura", "kheda", "gandhinagar", "deogarh", "ambedkar nagar", "ambassa",
    "khanna", "karur", "manali", "srinagar", "dwarka", "nalanda", "tarapur", "chatra", "vaishali", "chitrakoot",
    "shahjahanpur", "mewat", "rewari", "bhopal", "kalyani", "chamba", "nuh", "bijnor", "rajgarh", "hardoi",
}

# Place names that exist in several states: usable only as a hint that must agree with other evidence.
AMBIGUOUS_PLACES: dict[str, list[str]] = {
    "aurangabad": ["Maharashtra", "Bihar"],
    "bilaspur": ["Chhattisgarh", "Himachal Pradesh"],
    "hamirpur": ["Uttar Pradesh", "Himachal Pradesh"],
    "pratapgarh": ["Uttar Pradesh", "Rajasthan"],
    "balrampur": ["Uttar Pradesh", "Chhattisgarh"],
    "bijapur": ["Karnataka", "Chhattisgarh"],
    "udaipur": ["Rajasthan", "Tripura"],
    "lakhimpur": ["Uttar Pradesh", "Assam"],
    "bishnupur": ["West Bengal", "Manipur"],
    "mahe": ["Puducherry", "Kerala"],
    "sonepur": ["Odisha", "Bihar"],
    "fatehpur": ["Uttar Pradesh", "Rajasthan"],
}

# Institutions whose location is publicly well known -> state. Lowercase phrases, whole-word matched.
ALIASES: dict[str, str] = {
    "iit bombay": "Maharashtra",
    "indian institute of technology bombay": "Maharashtra",
    "barc": "Maharashtra",
    "bhabha atomic research centre": "Maharashtra",
    "mazagon dock": "Maharashtra",
    "mazagon": "Maharashtra",
    "jnpt": "Maharashtra",
    "jnpa": "Maharashtra",
    "jawaharlal nehru port": "Maharashtra",
    "mcgm": "Maharashtra",
    "brihanmumbai": "Maharashtra",
    "bruhanmumbai": "Maharashtra",
    "mmrda": "Maharashtra",
    "cidco": "Maharashtra",
    "midc": "Maharashtra",
    "mhada": "Maharashtra",
    "msedcl": "Maharashtra",
    "mahagenco": "Maharashtra",
    "mahatransco": "Maharashtra",
    "mahavitaran": "Maharashtra",
    "hindustan shipyard": "Andhra Pradesh",
    "cochin shipyard": "Kerala",
    "garden reach shipbuilders": "West Bengal",
    "goa shipyard": "Goa",
    "mishra dhatu nigam": "Telangana",
    "chittaranjan locomotive works": "West Bengal",
    "vikram sarabhai space centre": "Kerala",
    "space applications centre": "Gujarat",
}

# Phrases that contain a state name but are not geographic evidence (nation-wide institutions).
NEUTRAL_PHRASES: list[str] = [
    "punjab national bank", "punjab and sind bank", "punjab sind bank", "bank of maharashtra",
    "bank of baroda", "jammu and kashmir bank", "j and k bank", "andhra bank", "karnataka bank",
    "tamilnad mercantile bank", "maharashtra state co operative bank", "bombay stock exchange",
    "bombay high court", "madras high court", "delhi high court", "calcutta high court",
    "andhra pradesh high court", "punjab and haryana high court", "bank of kerala",
]

# India Post PIN: first three digits -> state where the first two digits are not enough.
# Checked longest-prefix first (6 digits, 3 digits, 2 digits).
PIN_PREFIX_3: dict[str, str | None] = {
    "403": "Goa",
    "605": None,  # Puducherry / Tamil Nadu mixed
    "244": None,  # Uttarakhand / Uttar Pradesh mixed
    "160": None,  # Chandigarh / Mohali (resolved by 6-digit rules below)
    "194": "Ladakh",
    "246": "Uttarakhand", "248": "Uttarakhand", "249": "Uttarakhand", "262": "Uttarakhand", "263": "Uttarakhand",
    "734": "West Bengal", "735": "West Bengal", "736": "West Bengal",
    "737": "Sikkim", "744": "Andaman and Nicobar Islands",
    "790": "Arunachal Pradesh", "791": "Arunachal Pradesh", "792": "Arunachal Pradesh",
    "793": "Meghalaya", "794": "Meghalaya",
    "795": "Manipur", "796": "Mizoram", "797": "Nagaland", "798": "Nagaland", "799": "Tripura",
    "814": "Jharkhand", "815": "Jharkhand", "816": "Jharkhand", "822": "Jharkhand",
    "825": "Jharkhand", "826": "Jharkhand", "827": "Jharkhand", "828": "Jharkhand", "829": "Jharkhand",
    "396": None,  # Gujarat / Dadra-Nagar Haveli-Daman: resolved by 6-digit rules
}

PIN_PREFIX_2: dict[str, str] = {
    "11": "Delhi",
    "12": "Haryana", "13": "Haryana",
    "14": "Punjab", "15": "Punjab",
    "16": "Punjab",
    "17": "Himachal Pradesh",
    "18": "Jammu and Kashmir", "19": "Jammu and Kashmir",
    "20": "Uttar Pradesh", "21": "Uttar Pradesh", "22": "Uttar Pradesh", "23": "Uttar Pradesh",
    "24": "Uttar Pradesh", "25": "Uttar Pradesh", "26": "Uttar Pradesh", "27": "Uttar Pradesh",
    "28": "Uttar Pradesh",
    "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan", "33": "Rajasthan", "34": "Rajasthan",
    "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat",
    "40": "Maharashtra", "41": "Maharashtra", "42": "Maharashtra", "43": "Maharashtra", "44": "Maharashtra",
    "45": "Madhya Pradesh", "46": "Madhya Pradesh", "47": "Madhya Pradesh", "48": "Madhya Pradesh",
    "49": "Chhattisgarh",
    "50": "Telangana",
    "51": "Andhra Pradesh", "52": "Andhra Pradesh", "53": "Andhra Pradesh",
    "56": "Karnataka", "57": "Karnataka", "58": "Karnataka", "59": "Karnataka",
    "60": "Tamil Nadu", "61": "Tamil Nadu", "62": "Tamil Nadu", "63": "Tamil Nadu", "64": "Tamil Nadu",
    "67": "Kerala", "68": "Kerala", "69": "Kerala",
    "70": "West Bengal", "71": "West Bengal", "72": "West Bengal", "73": "West Bengal", "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha",
    "78": "Assam",
    "80": "Bihar", "81": "Bihar", "82": "Bihar",
    "83": "Jharkhand",
    "84": "Bihar", "85": "Bihar",
}
