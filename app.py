import streamlit as st
import requests
import math
from groq import Groq
from streamlit_geolocation import streamlit_geolocation


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Pakistan AI Restaurant Finder",
    page_icon="🍽️",
    layout="wide"
)


# ============================================================
# API KEYS
# ============================================================

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error(
        "API keys are missing. Add GOOGLE_API_KEY and GROQ_API_KEY "
        "in Streamlit Cloud → App settings → Secrets."
    )
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)


# ============================================================
# PAKISTAN LOCATIONS
# These are fallback area centers when GPS is not used.
# ============================================================

LOCATIONS = {
    "Lahore": {
        "Gulberg": (31.5100, 74.3500),
        "MM Alam Road": (31.5143, 74.3560),
        "Liberty Market": (31.5116, 74.3436),
        "DHA Phase 4": (31.4697, 74.4080),
        "DHA Phase 5": (31.4667, 74.4100),
        "DHA Phase 6": (31.4730, 74.4320),
        "Johar Town": (31.4697, 74.2728),
        "Model Town": (31.4833, 74.3269),
        "Bahria Town": (31.3670, 74.1870),
        "Wapda Town": (31.4430, 74.2730),
        "Faisal Town": (31.4900, 74.3000),
        "Garden Town": (31.4960, 74.3240),
    },
    "Karachi": {
        "Clifton": (24.8138, 67.0300),
        "DHA Phase 5": (24.8007, 67.0575),
        "DHA Phase 6": (24.7936, 67.0635),
        "PECHS": (24.8660, 67.0720),
        "Gulshan-e-Iqbal": (24.9200, 67.0900),
        "North Nazimabad": (24.9450, 67.0320),
    },
    "Islamabad": {
        "F-6": (33.7290, 73.0700),
        "F-7": (33.7215, 73.0550),
        "F-8": (33.7080, 73.0450),
        "E-7": (33.7190, 73.0460),
        "G-9": (33.6880, 73.0350),
        "Bahria Town": (33.5480, 73.1380),
    },
    "Rawalpindi": {
        "Saddar": (33.5969, 73.0528),
        "Bahria Town": (33.5480, 73.1380),
        "Chaklala": (33.6060, 73.0990),
        "Satellite Town": (33.6400, 73.0700),
    },
    "Faisalabad": {
        "D Ground": (31.4060, 73.0790),
        "Peoples Colony": (31.4180, 73.0910),
        "Susan Road": (31.4040, 73.0880),
    },
    "Multan": {
        "Gulgasht Colony": (30.2140, 71.4680),
        "Cantt": (30.1980, 71.4430),
        "Bosan Road": (30.2470, 71.4890),
    },
    "Peshawar": {
        "University Town": (34.0100, 71.5250),
        "Hayatabad": (33.9950, 71.4300),
        "Saddar": (34.0060, 71.5370),
    },
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two GPS points."""
    earth_radius = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


def price_label(price_level):
    """Convert Google price level to a simple label."""
    price_map = {
        "PRICE_LEVEL_FREE": "Free",
        "PRICE_LEVEL_INEXPENSIVE": "Budget",
        "PRICE_LEVEL_MODERATE": "Moderate",
        "PRICE_LEVEL_EXPENSIVE": "Expensive",
        "PRICE_LEVEL_VERY_EXPENSIVE": "Very Expensive",
    }
    return price_map.get(price_level, "Not available")


def restaurant_name(place):
    display_name = place.get("displayName", {})
    if isinstance(display_name, dict):
        return display_name.get("text", "Unknown restaurant")
    return str(display_name)


# ============================================================
# GOOGLE PLACES - NEARBY SEARCH
# ============================================================

def find_restaurants(latitude, longitude, radius_km):
    """
    Find up to 15 restaurants near the supplied coordinates.
    Results are ranked by Google popularity.
    """

    url = "https://places.googleapis.com/v1/places:searchNearby"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.location,"
            "places.rating,"
            "places.userRatingCount,"
            "places.priceLevel,"
            "places.formattedAddress,"
            "places.googleMapsUri"
        ),
    }

    payload = {
        "includedTypes": ["restaurant"],
        "maxResultCount": 15,
        "rankPreference": "POPULARITY",
        "regionCode": "PK",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_km * 1000,
            }
        },
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            st.error("Google Places API error")
            st.code(response.text)
            return []

        return response.json().get("places", [])

    except Exception as error:
        st.error("Could not connect to Google Places.")
        st.code(str(error))
        return []


# ============================================================
# GOOGLE PLACES - PLACE DETAILS
# ============================================================

def get_restaurant_details(place_id):
    """
    Get detailed information for one restaurant.
    Google Places can return up to 5 review objects.
    """

    url = f"https://places.googleapis.com/v1/places/{place_id}"

    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "id,"
            "displayName,"
            "formattedAddress,"
            "rating,"
            "userRatingCount,"
            "priceLevel,"
            "priceRange,"
            "reviews,"
            "websiteUri,"
            "googleMapsUri,"
            "location"
        ),
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            return {}

        return response.json()

    except Exception:
        return {}


# ============================================================
# REVIEW EXTRACTION
# ============================================================

def localized_text(value):
    """Extract text from Google's LocalizedText object."""
    if isinstance(value, dict):
        return value.get("text", "")
    if value:
        return str(value)
    return ""


def extract_reviews(details):
    """
    Extract original customer review text when available.

    originalText is preferred because it preserves the original
    customer wording, which is important for Roman Urdu.
    """

    review_objects = details.get("reviews", [])
    reviews = []

    for review in review_objects:
        original_text = localized_text(review.get("originalText"))
        translated_text = localized_text(review.get("text"))

        text = original_text.strip() or translated_text.strip()

        if not text:
            continue

        reviews.append(
            {
                "text": text,
                "rating": review.get("rating", ""),
                "date": review.get(
                    "relativePublishTimeDescription",
                    ""
                ),
            }
        )

    return reviews


# ============================================================
# GROQ AI ANALYSIS
# ============================================================

def analyze_restaurant(name, address, reviews, official_website):
    """
    Analyze available Google customer reviews.

    Groq Compound can use web search when needed. The prompt
    tells it to prioritize the official restaurant website for
    menu/specialty verification.

    Customer evidence remains the primary source for the verdict.
    """

    review_text = "\n\n".join(
        [
            (
                f"Customer Review {i + 1}\n"
                f"Rating: {review.get('rating', 'N/A')}\n"
                f"Time: {review.get('date', 'N/A')}\n"
                f"Text: {review.get('text', '')}"
            )
            for i, review in enumerate(reviews)
        ]
    )

    website_text = official_website or "No official website was provided by Google."

    prompt = f"""
You are the evidence-based restaurant analyst for a Pakistan
restaurant discovery application.

RESTAURANT
Name: {name}
Address: {address}

OFFICIAL RESTAURANT WEBSITE
{website_text}

GOOGLE CUSTOMER REVIEW EVIDENCE
{review_text}

IMPORTANT SOURCE RULES

1. CUSTOMER REVIEWS ARE THE PRIMARY EVIDENCE for:
   - popular dishes
   - frequently mentioned dishes
   - best dishes to try
   - customer likes
   - complaints
   - service experience
   - food quality
   - value for money
   - final recommendation

2. The official restaurant website may be used to VERIFY:
   - whether a mentioned dish exists on the official menu
   - official menu items
   - restaurant specialties
   - official restaurant information

3. If the official website is available, use Groq's web search/website
   tools when useful to inspect the official website.

4. DO NOT use general food knowledge as proof that a dish is popular.

5. DO NOT invent a dish, review, customer opinion, price, or experience.

6. If a dish is on the official website but customers did not mention it,
   say that it is officially listed but there is insufficient customer
   evidence to call it popular or recommended.

ROMAN URDU AND MIXED LANGUAGE

Customer reviews may be written in:
- English
- Roman Urdu
- Urdu-English mixed language
- informal Pakistani English
- slang or abbreviated Roman Urdu

You MUST understand the meaning and sentiment of Roman Urdu.

Examples:

"biryani bohat zabardast thi"
= strong positive evidence for biryani

"karahi ka taste acha tha lekin service slow thi"
= positive food feedback for karahi + negative service feedback

"quantity achi thi"
= positive portion/quantity feedback

"bohat dair lagi"
= negative waiting/service feedback

"paisa wasool"
= positive value-for-money feedback

"mehnga tha"
= price/value concern

"dobara nahi khaunga"
= negative repeat-intent signal

Do NOT translate Roman Urdu mechanically and lose its meaning.
Understand the complete sentence and its context.

MIXED LANGUAGE EXAMPLE

"Chicken karahi zabardast thi but naan thanday thay."

Extract:
- Chicken Karahi -> positive
- Naan -> negative
- Complaint -> naan served cold

DISH ANALYSIS

Identify dishes explicitly mentioned by customers.

Count repeated mentions when possible.

If one customer mentions a dish once, do NOT call it "the most
popular dish".

Use wording such as:
- "Frequently mentioned"
- "Repeated positive mentions"
- "Single positive mention"
- "Limited evidence"

BEST DISHES TO TRY

Recommend only dishes with positive customer evidence.

For each recommendation explain:
- number/strength of mentions when possible
- what customers liked
- whether the official website confirms that the dish is available

Never claim that you personally tasted the food.

CUSTOMER LIKES

Extract repeated positive themes such as:
- taste
- freshness
- portion size
- value
- service
- atmosphere
- specific dishes

CUSTOMER COMPLAINTS

Extract negative themes such as:
- poor taste
- small portions
- high price
- slow service
- waiting time
- cleanliness
- staff behavior

TRENDING / RECENT SIGNAL

Do NOT call something "trending" based on one review.

Only identify a recent signal if the supplied review dates support it.

If the evidence is insufficient, explicitly say:
"Insufficient evidence to identify a trending dish."

FINAL VERDICT

Answer:
YES
MAYBE
or
NO

The verdict MUST be based primarily on customer evidence.

If there are very few reviews, lower the confidence.

If customer evidence is unavailable, do not manufacture a verdict.

CONFIDENCE

Choose:
HIGH
MEDIUM
or
LOW

Confidence should reflect:
- number of available review texts
- consistency of customer feedback
- strength of dish mentions
- strength of positive/negative patterns

Return exactly these sections:

🍽️ FREQUENTLY MENTIONED DISHES

⭐ BEST DISHES TO TRY

👍 WHAT CUSTOMERS LIKE

⚠️ CUSTOMER COMPLAINTS

🔥 RECENT / TRENDING SIGNAL

🌐 OFFICIAL WEBSITE CHECK

🤖 CUSTOMER-BACKED VERDICT

📊 CONFIDENCE
"""

    system_message = """
You are a strict evidence-based restaurant review analyst.

You understand English, Roman Urdu, Urdu-English mixed reviews,
informal Pakistani language, and common Roman Urdu spelling variations.

Customer review evidence must remain separate from official website facts.

You may use the web when useful, especially to inspect the official
restaurant website supplied by the application.

Never invent customer evidence.

Never pretend you tasted food.

Never call a dish popular or best without customer evidence.

When evidence is weak, say so clearly.
"""

    try:
        response = groq_client.chat.completions.create(
            model="groq/compound",
            messages=[
                {
                    "role": "system",
                    "content": system_message,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message.content

    except Exception as error:
        return f"AI analysis failed.\n\nError: {str(error)}"


# ============================================================
# STREAMLIT UI
# ============================================================

st.title("🍽️ Pakistan AI Restaurant Finder")

st.write(
    "Find the top 15 nearby restaurants and discover what "
    "customers actually say about them."
)

st.info(
    "AI recommendations are based primarily on available customer "
    "review text. Roman Urdu and mixed English/Roman Urdu reviews "
    "are also analyzed."
)


# ============================================================
# SIDEBAR - LOCATION
# ============================================================

st.sidebar.header("📍 Restaurant Search")

st.sidebar.subheader("Your Current Location")

# Browser location component.
# The user must allow location access in the browser.
location = streamlit_geolocation()

user_lat = None
user_lon = None
location_accuracy = None

if location:
    user_lat = location.get("latitude")
    user_lon = location.get("longitude")
    location_accuracy = location.get("accuracy")

if user_lat is not None and user_lon is not None:

    st.sidebar.success("Current location detected")

    if location_accuracy:
        st.sidebar.caption(
            f"GPS accuracy: approximately {location_accuracy:.0f} m"
        )

    use_current_location = st.sidebar.checkbox(
        "Use my current location",
        value=True,
    )

else:

    use_current_location = False

    st.sidebar.info(
        "Allow browser location access to find restaurants "
        "around your current position."
    )


# ============================================================
# FALLBACK CITY / AREA
# ============================================================

city = st.sidebar.selectbox(
    "Fallback city",
    list(LOCATIONS.keys()),
)

area = st.sidebar.selectbox(
    "Fallback area",
    list(LOCATIONS[city].keys()),
)

radius = st.sidebar.slider(
    "Search radius (km)",
    min_value=1,
    max_value=10,
    value=5,
)


if use_current_location and user_lat is not None and user_lon is not None:

    search_lat = user_lat
    search_lon = user_lon
    search_label = "your current location"

else:

    search_lat, search_lon = LOCATIONS[city][area]
    search_label = f"{area}, {city}"


st.sidebar.caption(
    "Distance is calculated from the search location to each restaurant."
)


# ============================================================
# SEARCH BUTTON
# ============================================================

if st.sidebar.button(
    "🔎 Find Top 15 Restaurants",
    use_container_width=True,
):

    with st.spinner("Finding nearby restaurants..."):

        restaurants = find_restaurants(
            search_lat,
            search_lon,
            radius,
        )

    if not restaurants:

        st.warning(
            "No restaurants were found in this search area."
        )

    else:

        st.session_state["restaurants"] = restaurants
        st.session_state["search_lat"] = search_lat
        st.session_state["search_lon"] = search_lon
        st.session_state["search_label"] = search_label

        st.success(
            f"Found {len(restaurants)} restaurants."
        )


# ============================================================
# SHOW RESTAURANTS
# ============================================================

if "restaurants" in st.session_state:

    restaurants = st.session_state["restaurants"]

    search_lat = st.session_state["search_lat"]
    search_lon = st.session_state["search_lon"]
    search_label = st.session_state["search_label"]

    st.markdown(
        f"## 📍 Top Restaurants Near {search_label}"
    )

    st.caption(
        "Showing up to 15 restaurants ranked by Google popularity."
    )

    for index, restaurant in enumerate(restaurants):

        name = restaurant_name(restaurant)

        rating = restaurant.get(
            "rating",
            "N/A",
        )

        review_count = restaurant.get(
            "userRatingCount",
            0,
        )

        address = restaurant.get(
            "formattedAddress",
            "Address unavailable",
        )

        location_data = restaurant.get(
            "location",
            {},
        )

        restaurant_lat = location_data.get(
            "latitude"
        )

        restaurant_lon = location_data.get(
            "longitude"
        )

        # Calculate actual distance from search location.
        if (
            restaurant_lat is not None
            and restaurant_lon is not None
        ):

            distance_value = calculate_distance_km(
                search_lat,
                search_lon,
                restaurant_lat,
                restaurant_lon,
            )

            distance = f"{distance_value:.2f} km"

        else:

            distance = "N/A"

        price = price_label(
            restaurant.get("priceLevel")
        )

        maps_url = restaurant.get(
            "googleMapsUri",
            "",
        )

        st.markdown("---")

        col1, col2 = st.columns(
            [3, 1]
        )

        with col1:

            st.subheader(
                f"{index + 1}. {name}"
            )

            st.write(
                f"⭐ Rating: {rating}"
            )

            st.write(
                f"💬 Google ratings/reviews: {review_count}"
            )

            st.write(
                f"📍 Distance from {search_label}: {distance}"
            )

            st.write(
                f"💰 Price: {price}"
            )

            st.write(
                f"🏠 {address}"
            )

        with col2:

            if maps_url:

                st.link_button(
                    "🗺️ Google Maps",
                    maps_url,
                    use_container_width=True,
                )

            analyze_button = st.button(
                "🤖 Analyze with AI",
                key=f"analyze_{index}",
                use_container_width=True,
            )

        # ====================================================
        # AI ANALYSIS
        # ====================================================

        if analyze_button:

            with st.spinner(
                "Getting customer review evidence..."
            ):

                details = get_restaurant_details(
                    restaurant["id"]
                )

                reviews = extract_reviews(
                    details
                )

            official_website = details.get(
                "websiteUri",
                "",
            )

            total_reviews = details.get(
                "userRatingCount",
                review_count,
            )

            st.markdown("### 🔎 Evidence Available")

            evidence_col1, evidence_col2, evidence_col3 = st.columns(3)

            with evidence_col1:
                st.metric(
                    "Google rating",
                    str(details.get("rating", rating)),
                )

            with evidence_col2:
                st.metric(
                    "Total Google ratings",
                    str(total_reviews),
                )

            with evidence_col3:
                st.metric(
                    "Review texts available",
                    str(len(reviews)),
                )

            if official_website:

                st.markdown(
                    "🌐 **Official restaurant website**"
                )

                st.link_button(
                    "Open Official Website",
                    official_website,
                )

            if maps_url:

                st.link_button(
                    "💬 Open Google Maps Reviews",
                    maps_url,
                )

            if not reviews:

                st.warning(
                    "Google provided no review text for AI analysis "
                    "for this restaurant."
                )

                st.info(
                    f"The restaurant has {total_reviews} Google "
                    "ratings/reviews in total, but the available "
                    "Places API response did not contain review text. "
                    "The app will NOT invent customer opinions."
                )

            else:

                st.success(
                    f"{len(reviews)} customer review text(s) "
                    "are available for AI analysis."
                )

                with st.expander(
                    "View customer review evidence"
                ):

                    for review_index, review in enumerate(
                        reviews,
                        start=1,
                    ):

                        st.markdown(
                            f"**Customer Review {review_index}**"
                        )

                        if review.get("rating"):
                            st.write(
                                f"⭐ Rating: {review['rating']}"
                            )

                        if review.get("date"):
                            st.write(
                                f"🕒 {review['date']}"
                            )

                        st.write(
                            review["text"]
                        )

                        st.markdown("---")

                with st.spinner(
                    "AI is analyzing English, Roman Urdu, "
                    "and mixed-language reviews..."
                ):

                    analysis = analyze_restaurant(
                        name=name,
                        address=address,
                        reviews=reviews,
                        official_website=official_website,
                    )

                st.markdown(
                    "### 🤖 Customer-Backed Analysis"
                )

                st.markdown(
                    analysis
                )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "Restaurant discovery and ratings: Google Places. "
    "Customer review evidence: available Google review text. "
    "AI analysis and official-site research: Groq Compound."
)
