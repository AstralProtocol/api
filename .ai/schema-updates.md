# Database Schema Updates

This document outlines planned changes to the database schema to better support location proof processing and storage.

## Location Proof Table Updates

### Core Location Data Improvements

1. **Original Location Data Storage**
   - Add `original_location_data JSONB` column to store the raw location data exactly as received from the chain
   - This preserves the original data for debugging, reprocessing, and transparency

2. **SRS Handling**
   - Rename `srs` to `original_srs VARCHAR(50)` to clarify it's from the attestation
   - Add `srid INTEGER DEFAULT 4326` for PostGIS compatibility (EPSG:4326 = WGS84)
   - All geometries in the database will be stored in WGS84 regardless of original SRS

3. **Data Quality Tracking**
   - Add `data_quality VARCHAR(20)` to indicate confidence in our interpretation:
     - `high`: Standard format, parsed correctly
     - `medium`: Required interpretation but likely correct
     - `low`: Significantly malformed but best effort made

4. **Complex Geometry Handling**
   - Add `is_collection BOOLEAN DEFAULT FALSE` to flag multi-feature data
   - Add `feature_count INTEGER DEFAULT 1` to track number of features in collections

### Media Data Improvements

Current issues:
- `media_type` and `media_data` are stored as JSON strings but should be arrays
- No structured way to associate media types with their data

Proposed solution:
- Create a new `media` table with foreign key to `location_proof`
- Each media item gets its own row with type, data, and metadata

```sql
CREATE TABLE media (
    id SERIAL PRIMARY KEY,
    location_proof_id INTEGER REFERENCES location_proof(id) ON DELETE CASCADE,
    media_type VARCHAR(100) NOT NULL,
    media_data TEXT NOT NULL,
    media_metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### Recipe Data Improvements

Similar to media data, recipe information could benefit from a dedicated table:

```sql
CREATE TABLE recipe (
    id SERIAL PRIMARY KEY,
    location_proof_id INTEGER REFERENCES location_proof(id) ON DELETE CASCADE,
    recipe_type VARCHAR(100) NOT NULL,
    recipe_payload JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

## Implementation Considerations

### Migration Strategy

1. **Create New Columns First**
   - Add all new columns to existing tables
   - This allows for backward compatibility during transition

2. **Populate New Columns**
   - Write a migration script to populate new columns from existing data
   - Test thoroughly with sample data

3. **Create New Tables**
   - Add media and recipe tables
   - Migrate existing JSON data to new table structures

4. **Update Application Code**
   - Modify ETL process to use new schema
   - Update API endpoints to serve data from new structure

### PostGIS Compatibility

- Ensure all spatial operations use the `srid` field for proper spatial calculations
- Use `ST_SetSRID` when creating geometries to ensure proper SRID assignment
- Consider adding spatial indexes on the geometry column

### API Impact

- Document changes in API responses
- Consider versioning the API to handle the transition
- Ensure GeoJSON output is compliant with the specification

## Open Questions

1. **FeatureCollection Handling**
   - How should we serve FeatureCollections via the API?
   - Can we wrap multiple features in a single feature? (Probably not ideal)
   - Should we return a FeatureCollection with a single feature that contains multiple geometries?

2. **Coordinate Order**
   - How aggressively should we try to detect and fix coordinate order issues?
   - Should we add a flag to indicate when we've swapped coordinates?

3. **Schema Evolution**
   - How do we handle future changes to the EAS schema?
   - Should we version our location proof schema?

## Next Steps

1. Review this schema proposal
2. Create SQL migration scripts
3. Update the ETL process to use the new schema
4. Test with various location data formats
5. Update API to serve data from the new schema
