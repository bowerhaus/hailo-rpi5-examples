# Watcher API Documentation

This document outlines the REST API endpoints available in the Watcher application's webserver.py.

## Authentication Endpoints

### Login

Authenticates a user and returns a JWT token.

```
POST /api/login
```

**Request Body**:
```json
{
  "username": "user123",
  "password": "securepassword"
}
```

**Response**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Register User

Registers a new user (requires authentication).

```
POST /api/register
```

**Request Body**:
```json
{
  "username": "newuser",
  "password": "securepassword"
}
```

**Response**:
```json
{
  "success": true
}
```

## Data Retrieval Endpoints

### Get CPU Temperature

Retrieves the current CPU temperature of the device.

```
GET /api/cpu_temperature
```

**Response**:
```json
{
  "cpu_temp": 45.2
}
```

### Get Available Dates

Returns a list of dates for which detection events are available.

```
GET /api/dates
```

**Response**:
```json
[
  "20230601",
  "20230602",
  "20230603"
]
```

### Get Image Files

Returns a list of image files for a specific date.

```
GET /api/files?date={date}
```

**Parameters**:
- `date`: Date string in YYYYMMDD format (optional, defaults to current date)

**Response**:
```json
[
  "event_20230601_123045.jpg",
  "event_20230601_134522.jpg"
]
```

### Get Metadata List

Retrieves a list of metadata files for a specific date.

```
GET /api/metadata?date={date}
```

**Parameters**:
- `date`: Date string in YYYYMMDD format (optional, defaults to current date)

**Response**:
```json
[
  "event_20230601_123045.json",
  "event_20230601_134522.json"
]
```

## Data Modification Endpoints

### Update Metadata Entry

Updates a metadata JSON file with new information.

```
POST /api/update/{filename}?date={date}
```

**Parameters**:
- `filename`: The JSON filename to update
- `date`: Date string in YYYYMMDD format (optional, defaults to current date)

**Request Body**:
```json
{
  "named_direction": "OUT",
  "label": "HELEN_OUT",
  "reviewed": true,
  "timestamp": "2023-06-01T12:30:45",
  "detection": {
    "score": 0.92,
    "bbox": [120, 150, 320, 450]
  }
}
```

**Response**:
- Status: 200 OK if successful

### Delete Entry

Deletes a detection event and its associated files.

```
DELETE /api/delete/{baseFilename}?date={date}
```

**Parameters**:
- `baseFilename`: The base filename without extension
- `date`: Date string in YYYYMMDD format (optional, defaults to current date)

**Response**:
```json
{
  "success": true,
  "deleted_files": [
    "event_20230601_123045.json",
    "event_20230601_123045.jpg",
    "event_20230601_123045.mp4"
  ]
}
```

## Media Files

The application serves media files via:

```
GET /media/{filename}
```

This serves various file types stored in the date-organized directories:
- JSON metadata files
- JPG image files
- MP4 video files

## Page Endpoints

### Login Page

```
GET /login
```

Returns the login HTML page and clears any existing authentication token.

### Home Page

```
GET /
```

Returns the main application home page (requires authentication).

### Review Page

```
GET /review
```

Returns the detection events review interface (requires authentication).