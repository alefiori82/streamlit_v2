#Import Python Libraries
import pandas as pd
import folium #to install folium using Anaconda: conda install -c conda-forge folium
import geopandas as gpd #to install geopandas, run this code in the conda terminal: conda install geopandas
from folium.features import GeoJsonTooltip
import streamlit as st #You can follow the instructions in the beginner tutorial to install Streamlit if you don't have it
from streamlit_folium import folium_static

@st.cache
def read_csv(path):
    return pd.read_csv(path, compression='gzip', sep='\t', quotechar='"')

housing_price_df=read_csv('county_market_tracker.tsv000.gz') #Replace ... with your file path
housing_price_df=housing_price_df[(housing_price_df['period_begin']>='2020-10-01') & (housing_price_df['period_begin']<='2021-10-01')] #only look at past 12 months' data
county_fips=pd.read_csv('county_fips.csv', sep='\t')
county_fips['region']=county_fips["Name"] + ' County, '+ county_fips["State"] #Create a new column called 'region' which is the concatenation of county name and state. This column will be used in the next step to join housing_price_df with county_fips

housing_price_df= housing_price_df.merge(county_fips, on="region", how="left") 
housing_price_df['FIPS'] = housing_price_df['FIPS'].astype(str).replace('\.0', '', regex=True)
housing_price_df["county_fips"] = housing_price_df["FIPS"].str.zfill(5)

@st.cache
def read_file(path):
    return gpd.read_file(path)

#Read the geojson file
gdf = read_file('georef-united-states-of-america-county.geojson')

#Merge the housing market data and geojson file into one dataframe
df_final = gdf.merge(housing_price_df, left_on="coty_code", right_on="county_fips", how="outer") #join housing_price_df with gdf to get the geometries column from geojson file
df_final= df_final[~df_final['period_begin'].isna()]  
df_final = df_final[~df_final['geometry'].isna()]
df_final=df_final[['period_begin','period_end', 'region','parent_metro_region','state_code',"property_type",'median_sale_price','median_sale_price_yoy','homes_sold','homes_sold_yoy','new_listings',
                   'new_listings_yoy','median_dom','avg_sale_to_list',"county_fips",'geometry']]
df_final.rename({'median_sale_price': 'Median Sales Price',
                 'median_sale_price_yoy': 'Median Sales Price (YoY)',
                 'homes_sold':'Homes Sold',
                 'homes_sold_yoy':'Homes Sold (YoY)',
                 'new_listings':'New Listings',
                 'new_listings_yoy':'New Listings (YoY)',
                 'median_dom':'Median Days-on-Market',
                 'avg_sale_to_list':'Avg Sales-to-Listing Price Ratio'}, 
                 axis=1, inplace=True) 

#st.write(df_final.head())  

#Adding a sidebar to the app
st.sidebar.title("Welcome Streamlitters!")

#Add filters/input widgets with tooltips
st.sidebar.markdown("Select Filters:") 


#Use forms and submit button to batch input widgets
with st.sidebar.form(key='columns_in_form'):
    period_list=df_final["period_begin"].unique().tolist()
    period_list.sort(reverse=True)
    year_month = st.selectbox("Snapshot Month", period_list, index=0, help='Choose by which time period you want to look at the metrics. The default is always the most recent month.')

    prop_type = st.selectbox(
                "View by Property Type", ['All Residential', 'Single Family Residential', 'Townhouse','Condo/Co-op','Single Units Only','Multi-Family (2-4 Unit)'] , index=0, help='select by which property type you want to look at the metrics. The default is all residential types.')

    metrics = st.selectbox("Select Housing Metrics", ["Median Sales Price","Median Sales Price (YoY)", "Homes Sold",'Homes Sold (YoY)','New Listings','New Listings (YoY)','Median Days-on-Market','Avg Sales-to-Listing Price Ratio'], index=0, help='You can view the map by different housing market metrics such as median sales price, homes sold, etc.')
    
    state_list=df_final["state_code"].unique().tolist()
    state_list.sort(reverse=False)
    state_list.insert(0,"All States")
    state = st.selectbox("Select State", state_list,index=0, help='select to either view the map for all the states or zoom into one state')
    
    homes_sold=st.slider("Sold >= X Number of Homes", min_value=1, max_value=500, value=10,help='Drag the slider to select counties that sold at least x number of homes in the snapshot month. By defaut we are showing counties that sold at least 10 homes in the snapshot month.')

    submitted = st.form_submit_button('Apply Filters')


# Pass the user input to the data frame
df_final=df_final[df_final["period_begin"]==year_month] #only show rows with period_begin equal to whatever selected by user as the time period
df_final=df_final[df_final["property_type"]==prop_type] #only show rows with property type equal to user's selection
df_final=df_final[df_final["Homes Sold"]>=homes_sold] #only show rows with at least X number of homes sold based on user's selection

#Define a function so that if user select 'all states' we'll show data for all the states. Otherwise only show data for whatever state selected by user
def state_filter (state):
   if state=='All States':
       df=df_final
   else: 
       df=df_final[df_final["state_code"]==state]
   return df
df_final=state_filter(state)  

#Quickly check whether the slicing and dicing of the dataframe works properly based on user's input
#st.write(df_final)

#Add a title and company logo
from PIL import Image
image = Image.open('logo.png')

col1, col2 = st.columns( [0.8, 0.2])
with col1:
    st.title("U.S. Real Estate Insights")   
with col2:
    st.image(image,  width=150)

#Add an expander to the app 
with st.expander("About the App"):
     st.write("""
         This app is created using Redfin Data Center's open data (https://www.redfin.com/news/data-center/) to visualize various housing market metrics across the U.S. states at county level. Areas that are white on the map are the counties that don't have data available. Select the filters on the sidebar and your insights are just a couple clicks away. Hover over the map to view more details.
     """)

#Create a choropleth map
col1, col2 = st.columns( [0.7, 0.3])
with col1:
    us_map = folium.Map(location=[40, -96], zoom_start=4,tiles=None)
    folium.TileLayer('CartoDB positron',name="Light Map",control=False).add_to(us_map)
    custom_scale = (df_final[metrics].quantile((0,0.6,0.7,0.8,0.9, 1))).tolist()

    folium.Choropleth(
            geo_data='georef-united-states-of-america-county.geojson',
            data=df_final,
            columns=['county_fips', metrics],  #Here we tell folium to get the county fips and plot the user-selected housing market metric for each county
            key_on='feature.properties.coty_code', #Here we grab the geometries/county boundaries from the geojson file using the key 'coty_code' which is the same as county fips
            threshold_scale=custom_scale, #use the custom scale we created for legend
            fill_color='YlGn',
            nan_fill_color="White", #Use white color if there is no data available for the county
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name='Measures',
            highlight=True,
            line_color='black').add_to(us_map) #by using .geojson.add_to() instead of .add_to() we are able to hide the legend. The reason why we want to hide the legend here is because the legend scale numbers are overlapping


    #Add Customized Tooltips to the map
    feature = folium.features.GeoJson(
                    data=df_final,
                    name='North Carolina',
                    smooth_factor=2,
                    style_function=lambda x: {'color':'black','fillColor':'transparent','weight':0.5},
                    tooltip=folium.features.GeoJsonTooltip(
                        fields=['period_begin',
                                'period_end',
                                'region',
                                'parent_metro_region',
                                'state_code',
                                "Median Sales Price",
                                "Median Sales Price (YoY)", 
                                "Homes Sold",'Homes Sold (YoY)',
                                'New Listings','New Listings (YoY)',
                                'Median Days-on-Market',
                                'Avg Sales-to-Listing Price Ratio'],
                        aliases=["Period Begin:",
                                    'Period End:',
                                    'County:',
                                    'Metro Area:',
                                    'State:',
                                    "Median Sales Price:",
                                "Median Sales Price (YoY):", 
                                "Homes Sold:",
                                'Homes Sold (YoY):',
                                'New Listings:',
                                'New Listings (YoY):',
                                'Median Days-on-Market:',
                                'Avg Sales-to-Listing Price Ratio:'], 
                        localize=True,
                        sticky=False,
                        labels=True,
                        style="""
                            background-color: #F0EFEF;
                            border: 2px solid black;
                            border-radius: 3px;
                            box-shadow: 3px;
                        """,
                        max_width=800,),
                            highlight_function=lambda x: {'weight':3,'fillColor':'grey'},
                        ).add_to(us_map)                    
        
    folium_static(us_map)

with col2:
    markdown_metrics = '<span style="color:black">**Metric**: '+metrics + '</span>'
    st.markdown(markdown_metrics, unsafe_allow_html=True)  #Overlay a text to the map which indicates which metric is shown on the choropleth map
