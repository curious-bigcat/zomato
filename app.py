import streamlit as st
import geocoder
import pandas as pd
from pymongo import MongoClient
import requests
import pydeck as pdk

# Function to connect to MongoDB Atlas
def connect_to_mongodb(uri):
    try:
        client = MongoClient(uri)
        db = client.zomato
        collection = db.restaurants
        return collection
    except Exception as e:
        st.error(f"Error connecting to MongoDB: {e}")
        return None

def detect_user_location(city=None):
    try:
        if city:
            location = geocoder.osm(city)
        else:
            location = geocoder.ip('me')
        
        if location.ok:
            return location
        else:
            st.warning("Unable to detect your location.")
            return None
    except Exception as e:
        st.error(f"Error detecting location: {e}")
        return None

def main():
    st.set_page_config(page_title="Find your Grub!!", layout="wide", initial_sidebar_state="expanded")
    
    # Set the color theme
    st.markdown("""
    <style>
    :root {
        --primary-color: #008080; /* Teal */
        --secondary-color: #333333; /* Dark Gray */
        --accent-color: #FFD700; /* Gold */
        --bg-color: #f5f5f5; /* Light Gray */
    }
    
    body {
        color: var(--secondary-color);
        background-color: var(--bg-color);
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: var(--primary-color);
    }
    
    a {
        color: var(--accent-color);
    }
    
    button, input, textarea {
        border-color: var(--accent-color);
    }
    
    .st-c5 {
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 10px;
        padding: 20px;
        background-color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("Find Your Grub!! 🍔🥗🍕")

    # Take user input for city
    user_city = st.text_input("Enter your city (Optional)")

    # Take user input for restaurant search
    restaurant_search_query = st.text_input("Search for a restaurant")

    # Detect user location
    location = detect_user_location(city=user_city)

    if location is None and not user_city:
        st.error("Failed to detect location. Please try again.")
        return

    # Connect to MongoDB Atlas
    collection = connect_to_mongodb("MONGODB_URL")
    if collection is None:
        return
    
    st.subheader("Your Current Location 📍")
    if location:
        st.write(f"Latitude: {location.latlng[0]}")
        st.write(f"Longitude: {location.latlng[1]}")
        st.write(f"City: {location.city}")
        st.write(f"Country: {location.country}")
    else:
        st.write("Location not available.")

    if not user_city and location:
        user_city = location.city

    # Display map
    map_container = st.container()
    with map_container:
        st.subheader(f"Map of Top Restaurants in {user_city}")
        
        # Query MongoDB collection to find matching "city"
        matching_documents = list(collection.find({"city": user_city}).sort("aggregate_rating", -1).limit(50))
        if matching_documents:
            map_data = pd.DataFrame({
                'latitude': [float(doc["latitude"]) for doc in matching_documents],
                'longitude': [float(doc["longitude"]) for doc in matching_documents],
                'name': [doc["name"] for doc in matching_documents],
                'type': [doc["type"] for doc in matching_documents],
                'address': [doc["address"] for doc in matching_documents]
            })
            
            view_state = pdk.ViewState(latitude=location.latlng[0] if location else 0, longitude=location.latlng[1] if location else 0, zoom=11, pitch=0)
            
            # Create the text layer
            text_layer = pdk.Layer(
                "TextLayer",
                data=map_data,
                get_position=["longitude", "latitude"],
                get_text="name",
                get_color=[255, 255, 255],
                get_size=12,
                get_alignment_baseline="bottom",
                pickable=True,
            )
            
            # Create the scatterplot layer with larger icons
            scatterplot_layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position=["longitude", "latitude"],
                get_radius=200,
                get_fill_color=[255, 0, 0],
                pickable=True,
            )
            
            map_ = pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=view_state,
                layers=[text_layer, scatterplot_layer],
                tooltip={"text": "{name}\nType: {type}\nAddress: {address}"},
                height=300
            )
            st.pydeck_chart(map_, use_container_width=False)
        else:
            st.write(f"No restaurants found in {user_city}")

    # Display top 25 restaurants in sidebar
    st.sidebar.subheader(f"Top Restaurants in {user_city} 🍽️")

    # Query MongoDB collection to find matching "city" for top 25 restaurants
    top_restaurants = list(collection.find({"city": user_city}).sort("aggregate_rating", -1).limit(25))
    if top_restaurants:
        for idx, doc in enumerate(top_restaurants):
            st.sidebar.markdown(f"**{idx + 1}. {doc['name']}**")
            st.sidebar.write(f"**Type:** {doc['type']}")
            st.sidebar.write(f"**Address:** {doc['address']}")
            st.sidebar.write("---")
    else:
        st.sidebar.write(f"No restaurants found in {user_city}")

    # Invoke API and print output
    if restaurant_search_query:
        api_url = "API_URL"
        payload = {"query": restaurant_search_query}
        response = requests.get(api_url, params=payload)
        if response.status_code == 200:
            st.write("API Response:")
            api_response = response.json()
            if "search_results" in api_response:
                search_results = api_response["search_results"]
                for result in search_results:
                    restaurant_name = result.get("name")
                    if restaurant_name:
                        # Query MongoDB collection to find the restaurant by name
                        restaurant_data = collection.find_one({"name": restaurant_name})
                        if restaurant_data:
                            # Create a new DataFrame with the required column names
                            restaurant_map_data = pd.DataFrame({
                                'lat': [float(restaurant_data["latitude"])],
                                'lon': [float(restaurant_data["longitude"])],
                                'name': [restaurant_data["name"]],
                            })

                            st.write(f"Restaurant Name: {restaurant_data['name']}")
                            st.write(f"Type: {restaurant_data['type']}")
                            st.write(f"Address: {restaurant_data['address']}")
                            st.write(f"City: {restaurant_data['city']}")
                            st.write(f"Cuisines: {restaurant_data['cuisines']}")
                            st.write(f"Timings: {restaurant_data['timings']}")
                            st.write(f"Highlights: {restaurant_data['highlights']}")
                            st.write(f"Latitude: {restaurant_data['latitude']}")
                            st.write(f"Longitude: {restaurant_data['longitude']}")

                            # Display the restaurant on the map
                            st.subheader("Restaurant Location on Map")
                            st.map(restaurant_map_data, zoom=12)
                        else:
                            st.write(f"Restaurant '{restaurant_name}' not found in the database.")
                    else:
                        st.write("No restaurant name found in the API response.")
            else:
                st.error("Error: Unable to fetch data from API.")

if __name__ == "__main__":
    main()
