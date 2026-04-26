Crime Mapping and Clustering Analytics System

An interactive geospatial crime exploration, clustering, analytics, and route tracing application built with Streamlit.

 Features

-Data Upload**: Upload crime data in Excel (.xlsx) format with required columns (Crime ID, Month, Reported by, Longitude, Latitude, Location, LSOA code, LSOA name, Outcome type).
- Crime Map**: Visualize crime locations on an interactive map with filters for crime type, month, and outcome.
- Routing**: Plan routes between points and trace roads on the map.
- Clustering**: Apply K-means and DBSCAN clustering algorithms to identify crime hotspots.
- Analytics Dashboard**: View statistical insights and visualizations of crime data.
- Download Filtered Data**: Export filtered crime data as CSV.

 Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd crime_mapping
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   streamlit run app.py
   ```

4. Access the app at `http://localhost:8501` and log in with:
   - Username: `admin`
   - Password: `crime@123`

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Usage

1. Upload your crime data Excel file.
2. Navigate through the sidebar to explore different features:
   - View crime maps with filters.
   - Perform clustering analysis.
   - Generate routes and analytics.
   - Download processed data.

 Project Structure

- `app.py`: Main Streamlit application.
- `analytics.py`: Analytics and visualization functions.
- `clustering.py`: Clustering algorithms (K-means, DBSCAN).
- `utils.py`: Utility functions for data processing and mapping.
- `requirements.txt`: Python dependencies.
- `assets/style.css`: Custom CSS styling.

Contributing

Contributions are welcome! Please open an issue or submit a pull request.
 License

This project is licensed under the MIT License.
