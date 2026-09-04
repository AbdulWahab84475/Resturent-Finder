import streamlit as st
import requests
import math
from groq import Groq


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Pakistan AI Restaurant Finder",
    page_icon="🍽️",
    layout="wide"
)


# =========================================================
# API KEYS
# =========================================================

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

groq_client = Groq(
    api_key=GROQ_API_KEY
)


# =========================================================
# PAKISTAN CITIES
# =========================================================

CITIES = {
    "Lahore": {
        "latitude": 31.5204,
        "longitude": 74.3587
    },

    "Karachi": {
        "latitude": 24.8607,
        "longitude": 67.0011
    },

    "Islamabad": {
        "latitude": 33.6844,
        "longitude": 73.0479
    },

    "Rawalpindi": {
        "latitude": 33.5651,
        "longitude": 73.0169
    },

    "Faisalabad": {
        "latitude": 31.4504,
        "longitude": 73.1350
    },

    "Multan": {
        "latitude": 30.1575,
        "longitude": 71.5249
    },

    "Peshawar": {
        "latitude": 34.0151,
        "longitude": 71.5249
    },

    "Gujranwala": {
        "latitude": 32.1877,
        "longitude": 74.1945
    }
}


# =========================================================
# FIND NEARBY RESTAURANTS
# =========================================================

def find_restaurants(latitude, longitude, radius_km):

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
            "places.formattedAddress"
        )
    }

    payload = {

        "includedTypes": [
            "restaurant"
        ],

        "maxResultCount": 10,

        "locationRestriction": {

            "circle": {

                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },

                "radius": radius_km * 1000
            }
        },

        "rankPreference": "DISTANCE"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:

        st.error("Google Places API error")

        st.code(response.text)

        return []

    data = response.json()

    return data.get(
        "places",
        []
    )


# =========================================================
# GET RESTAURANT DETAILS
# =========================================================

def get_restaurant_details(place_id):

    url = (
        f"https://places.googleapis.com/v1/places/{place_id}"
    )

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
            "location"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:

        st.error(
            "Could not get restaurant details."
        )

        st.code(response.text)

        return {}

    return response.json()


# =========================================================
# EXTRACT CUSTOMER REVIEWS
# =========================================================

def extract_reviews(details):

    reviews = details.get(
        "reviews",
        []
    )

    review_texts = []

    for review in reviews:

        text = (
            review
            .get("text", {})
            .get("text", "")
        )

        if text:

            review_texts.append(text)

    return review_texts


# =========================================================
# CALCULATE DISTANCE
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    earth_radius = 6371

    lat1 = math.radians(lat1)

    lat2 = math.radians(lat2)

    delta_lat = math.radians(
        lat2 - lat1
    )

    delta_lon = math.radians(
        lon2 - lon1
    )

    a = (

        math.sin(delta_lat / 2) ** 2

        +

        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(delta_lon / 2) ** 2

    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# =========================================================
# PRICE LEVEL
# =========================================================

def format_price(price_level):

    price_map = {

        "PRICE_LEVEL_FREE":
            "Free",

        "PRICE_LEVEL_INEXPENSIVE":
            "Budget",

        "PRICE_LEVEL_MODERATE":
            "Moderate",

        "PRICE_LEVEL_EXPENSIVE":
            "Expensive",

        "PRICE_LEVEL_VERY_EXPENSIVE":
            "Very Expensive"
    }

    return price_map.get(
        price_level,
        "Not available"
    )


# =========================================================
# AI RESTAURANT ANALYSIS
# =========================================================

def analyze_restaurant(
    restaurant_name,
    reviews
):

    if not reviews:

        return (
            "There are not enough customer reviews "
            "to provide a reliable recommendation."
        )

    review_text = "\n\n".join(

        f"Customer Review {i + 1}: {review}"

        for i, review in enumerate(reviews)
    )

    prompt = f"""
You are an evidence-based restaurant review analyst.

Restaurant:
{restaurant_name}

CUSTOMER REVIEWS:
{review_text}


TASK

Analyze the customer reviews carefully.


1. POPULAR DISHES

Identify dishes that customers explicitly mention.

Only identify dishes that actually appear
in the customer reviews.

Do not invent dishes.


2. CUSTOMERS LIKE

Identify things customers liked.

Focus on repeated or meaningful positive feedback.


3. CUSTOMER COMPLAINTS

Identify negative feedback and complaints.

Include issues such as:

- food quality
- taste
- portion size
- price
- service
- waiting time
- cleanliness
- atmosphere


4. DISH RESEARCH

Research dishes that customers explicitly mentioned.

Use web research only to provide general factual
context about those dishes.

IMPORTANT:

Customer reviews are the primary evidence.

External research is ONLY context.

Do not use external information as proof
that customers liked a dish.


5. CUSTOMER-BACKED VERDICT

Answer:

"Based on the available customer evidence,
would you recommend trying this restaurant?"

The recommendation must be based primarily
on customer feedback.


6. CONFIDENCE

Give:

High
Medium
or Low

based on the amount and consistency
of available customer evidence.


IMPORTANT RULES

- Never invent dishes.
- Never invent customer opinions.
- Never pretend you tasted the food.
- Do not call something popular based on
  general internet knowledge.
- Do not claim "best" without strong evidence.
- Mention important negative feedback.
- If evidence is insufficient, clearly say so.


Return these sections:

POPULAR DISHES

CUSTOMERS LIKE

CUSTOMER COMPLAINTS

DISH RESEARCH

CUSTOMER-BACKED VERDICT

CONFIDENCE
"""

    response = groq_client.chat.completions.create(

        model="groq/compound",

        messages=[

            {
                "role": "system",

                "content": (
                    "You are a careful restaurant "
                    "review analyst. Separate "
                    "customer evidence from "
                    "external research."
                )
            },

            {
                "role": "user",

                "content": prompt
            }

        ]
    )

    return (
        response
        .choices[0]
        .message
        .content
    )


# =========================================================
# STREAMLIT USER INTERFACE
# =========================================================

st.title(
    "🍽️ Pakistan AI Restaurant Finder"
)

st.write(
    "Find nearby restaurants in Pakistan "
    "and get an evidence-based recommendation "
    "using customer reviews."
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header(
    "Restaurant Search"
)

city = st.sidebar.selectbox(
    "Select city",
    list(CITIES.keys())
)

radius = st.sidebar.slider(
    "Search radius (km)",
    min_value=1,
    max_value=10,
    value=3
)


# =========================================================
# SEARCH BUTTON
# =========================================================

if st.sidebar.button(
    "Find Restaurants"
):

    city_data = CITIES[city]

    with st.spinner(
        "Finding nearby restaurants..."
    ):

        restaurants = find_restaurants(

            city_data["latitude"],

            city_data["longitude"],

            radius
        )

    if not restaurants:

        st.warning(
            "No restaurants found."
        )

    else:

        st.success(
            f"Found {len(restaurants)} restaurants "
            f"in {city}."
        )

        # Store restaurants in session
        st.session_state["restaurants"] = restaurants

        st.session_state["city"] = city


# =========================================================
# DISPLAY RESTAURANTS
# =========================================================

if "restaurants" in st.session_state:

    restaurants = st.session_state["restaurants"]

    city = st.session_state["city"]

    city_data = CITIES[city]

    for index, restaurant in enumerate(
        restaurants
    ):

        name = (
            restaurant
            .get("displayName", {})
            .get(
                "text",
                "Unknown restaurant"
            )
        )

        rating = restaurant.get(
            "rating",
            "N/A"
        )

        review_count = restaurant.get(
            "userRatingCount",
            0
        )

        address = restaurant.get(
            "formattedAddress",
            "Address not available"
        )

        price = format_price(
            restaurant.get(
                "priceLevel"
            )
        )

        location = restaurant.get(
            "location",
            {}
        )

        restaurant_lat = location.get(
            "latitude"
        )

        restaurant_lon = location.get(
            "longitude"
        )

        distance = "N/A"

        if (
            restaurant_lat is not None
            and restaurant_lon is not None
        ):

            distance_value = calculate_distance(

                city_data["latitude"],

                city_data["longitude"],

                restaurant_lat,

                restaurant_lon
            )

            distance = (
                f"{distance_value:.2f} km"
            )


        # -------------------------------------------------
        # RESTAURANT CARD
        # -------------------------------------------------

        st.markdown("---")

        col1, col2 = st.columns(
            [3, 1]
        )

        with col1:

            st.subheader(
                name
            )

            st.write(
                f"⭐ Rating: {rating}"
            )

            st.write(
                f"💬 Reviews: {review_count}"
            )

            st.write(
                f"📍 Distance: {distance}"
            )

            st.write(
                f"💰 Price: {price}"
            )

            st.write(
                f"🏠 {address}"
            )


        with col2:

            # Google Maps button

            if (
                restaurant_lat is not None
                and restaurant_lon is not None
            ):

                maps_url = (
                    "https://www.google.com/maps/search/"
                    "?api=1"
                    f"&query={restaurant_lat},"
                    f"{restaurant_lon}"
                )

                st.link_button(
                    "🗺️ Google Maps",
                    maps_url
                )


            # AI button

            analyze_button = st.button(

                "🤖 Analyze with AI",

                key=f"analyze_{index}"
            )


        # -------------------------------------------------
        # AI ANALYSIS
        # -------------------------------------------------

        if analyze_button:

            with st.spinner(
                "Reading customer reviews..."
            ):

                details = get_restaurant_details(
                    restaurant["id"]
                )

                reviews = extract_reviews(
                    details
                )


            if not reviews:

                st.warning(
                    "No customer review text "
                    "was available for this restaurant."
                )

            else:

                st.info(
                    f"Analyzing {len(reviews)} "
                    "available customer reviews."
                )

                with st.spinner(
                    "Analyzing reviews and researching dishes..."
                ):

                    analysis = analyze_restaurant(

                        name,

                        reviews
                    )

                st.markdown(
                    "### 🤖 Customer-Backed Analysis"
                )

                st.markdown(
                    analysis
                )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Recommendations are based on available "
    "customer-review evidence. External dish "
    "research is used only as supporting context."
)
