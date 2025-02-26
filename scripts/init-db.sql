-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable PostGIS topology extension
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Enable PostGIS raster extension
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- Enable PostGIS SFCGAL extension
CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;

-- Enable additional PostGIS extensions
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS address_standardizer;
CREATE EXTENSION IF NOT EXISTS address_standardizer_data_us;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Set up permissions
GRANT ALL PRIVILEGES ON DATABASE astral TO postgres;
