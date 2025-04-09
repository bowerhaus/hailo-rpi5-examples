# Pigeonator Web Server API Documentation

This document describes all the API endpoints available in the Pigeonator web service.

## Endpoints

### List Image Files

Get a list of image files for the current day.

- **URL**: `/api/files`
- **Method**: `GET`
- **Response**: JSON array of image filenames sorted with newest first

**Example Response**:
```json
["20240601_121505_x3_2.jpg", "20240601_121500_x2_1.jpg", "20240601_120045_x1_1.jpg"]
```

### List Metadata Files

Get a list of JSON metadata files for a specific date.

- **URL**: `/api/metadata`
- **Method**: `GET`
- **URL Parameters**:
  - `date`: Date in YYYYMMDD format (optional, defaults to current date)
  - `since`: Timestamp in seconds since epoch. Only returns files newer than this timestamp (optional).
- **Response**: JSON array of metadata filenames sorted with newest first

**Example Response**:
```json
["20240601_121505_x3_2.json", "20240601_121500_x2_1.json", "20240601_120045_x1_1.json"]
```

### Update JSON Metadata

Update a metadata JSON file.

- **URL**: `/api/update/<filename>`
- **Method**: `POST`
- **URL Parameters**:
  - `date`: Date in YYYYMMDD format (optional, defaults to current date)
  - `filename`: Name of the JSON file to update
- **Request Body**: JSON object with updated metadata
- **Response**: Success or error message

**Example Request**:
```json
{
  "classification": "pigeon",
  "confidence": 0.92,
  "notes": "Gray pigeon with iridescent neck"
}
```

**Example Response**:
```json
{"success": true}
```

### Delete Files

Delete all files matching a base filename.

- **URL**: `/api/delete/<base_filename>`
- **Method**: `DELETE`
- **URL Parameters**:
  - `date`: Date in YYYYMMDD format (optional, defaults to current date) 
  - `base_filename`: Base filename to match for deletion
- **Response**: JSON object with deletion status and list of deleted files

**Example Response**:
```json
{
  "success": true, 
  "deleted_files": ["20240601_121505_x3_2.jpg", "20240601_121505_x3_2.json", "20240601_121505_x3_2[1].jpg"]
}
```

### Serve Media

Serve a media file (image, JSON, or video).

- **URL**: `/media/<filename>`
- **Method**: `GET`
- **URL Parameters**:
  - `filename`: Name of the media file (must start with date in YYYYMMDD format)
- **Response**: The requested media file or an error message

### List Available Dates

Get a list of all dates that have media files.

- **URL**: `/api/dates`
- **Method**: `GET`
- **Response**: JSON array of available dates in YYYYMMDD format, sorted newest first

**Example Response**:
```json
["20240601", "20240531", "20240530", "20240529"]
```

### Get CPU Temperature

Get the current CPU temperature of the device.

- **URL**: `/api/cpu_temperature`
- **Method**: `GET`
- **Response**: JSON object with current temperature in degrees Celsius

**Example Response**:
```json
{"temperature": 56.7}
```

## Error Responses

All endpoints return appropriate HTTP status codes:

- `200 OK`: Request successful
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

Error responses include a JSON object with an error message:

```json
{"error": "Error message description"}
```