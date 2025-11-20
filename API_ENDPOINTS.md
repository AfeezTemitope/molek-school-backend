# 🌐 API ENDPOINTS DOCUMENTATION

Complete reference for all MOLEK School Admin API endpoints.

---

## 📋 TABLE OF CONTENTS

1. [Authentication](#authentication)
2. [Admin Management](#admin-management)
3. [Profile Management](#profile-management)
4. [Content Management](#content-management)
5. [Gallery Management](#gallery-management)
6. [Response Formats](#response-formats)
7. [Error Handling](#error-handling)

---

## 🔐 AUTHENTICATION

### Login (Obtain JWT Tokens)

```http
POST /api/token/
```

**Description**: Authenticate admin user and obtain JWT access and refresh tokens.

**Request Body**:
```json
{
  "username": "admin",
  "password": "secure_password"
}
```

**Response** (200 OK):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@molekschool.com",
    "first_name": "John",
    "last_name": "Doe",
    "full_name": "John Doe",
    "role": "superadmin",
    "phone_number": "+2341234567890",
    "is_active": true,
    "age": 35,
    "sex": "male",
    "address": "123 Main St",
    "state_of_origin": "Lagos",
    "local_govt_area": "Ikeja"
  }
}
```

**Authentication**: None (Public endpoint)

**Notes**:
- Only users with `admin` or `superadmin` role can login
- Access token expires in 15 minutes
- Refresh token expires in 7 days
- Store both tokens securely in client

---

### Refresh JWT Token

```http
POST /api/token/refresh/
```

**Description**: Obtain a new access token using a valid refresh token.

**Request Body**:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response** (200 OK):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Authentication**: None (requires valid refresh token)

**Notes**:
- Use this endpoint when access token expires
- Refresh token can only be used once if rotation is enabled
- Automatically handled by frontend axios interceptor

---

## 👥 ADMIN MANAGEMENT

### List All Admins

```http
GET /api/admins/
```

**Description**: Retrieve a paginated list of all active admin and superadmin users.

**Query Parameters**:
- `search` (string): Search by username, email, first name, or last name
- `role` (string): Filter by role (`admin` or `superadmin`)
- `is_active` (boolean): Filter by active status
- `ordering` (string): Sort results (e.g., `-created_at`, `username`)
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Results per page (default: 20)

**Example Request**:
```http
GET /api/admins/?search=john&role=admin&page=1
```

**Response** (200 OK):
```json
{
  "count": 45,
  "next": "http://api.example.com/api/admins/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "username": "johndoe",
      "email": "john@molekschool.com",
      "first_name": "John",
      "last_name": "Doe",
      "full_name": "John Doe",
      "role": "admin",
      "phone_number": "+2341234567890",
      "is_active": true,
      "age": 32,
      "sex": "male",
      "address": "123 Main St",
      "state_of_origin": "Lagos",
      "local_govt_area": "Ikeja",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:45:00Z"
    }
  ]
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Only returns users with `admin` or `superadmin` roles
- Results are optimized with minimal database queries
- Soft-deleted users (is_active=false) are excluded

---

### Create New Admin

```http
POST /api/admins/
```

**Description**: Create a new admin or superadmin user.

**Request Body**:
```json
{
  "username": "newadmin",
  "email": "newadmin@molekschool.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "secure_password123",
  "role": "admin",
  "phone_number": "+2341234567890",
  "age": 28,
  "sex": "female",
  "address": "456 School Ave",
  "state_of_origin": "Lagos",
  "local_govt_area": "Surulere"
}
```

**Response** (201 Created):
```json
{
  "id": 25,
  "username": "newadmin",
  "email": "newadmin@molekschool.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "full_name": "Jane Smith",
  "role": "admin",
  "phone_number": "+2341234567890",
  "is_active": true,
  "age": 28,
  "sex": "female",
  "address": "456 School Ave",
  "state_of_origin": "Lagos",
  "local_govt_area": "Surulere",
  "created_at": "2024-11-20T15:30:00Z",
  "updated_at": "2024-11-20T15:30:00Z"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Validation Rules**:
- `username`: Required, unique, 1-150 characters
- `email`: Required, unique, valid email format
- `first_name`: Required, 1-150 characters
- `last_name`: Required, 1-150 characters
- `password`: Required, minimum 8 characters
- `role`: Must be `admin` or `superadmin`
- `phone_number`: Optional, 9-15 digits with optional +
- `age`: Optional, 1-120

**Role Restrictions**:
- **Admins** can create other admins but NOT superadmins
- **Superadmins** can create both admins and superadmins

**Notes**:
- Password is automatically hashed before storage
- Username cannot be changed after creation
- User is automatically set as active (is_active=true)

---

### Get Admin Details

```http
GET /api/admins/{id}/
```

**Description**: Retrieve detailed information about a specific admin user.

**Path Parameters**:
- `id` (integer): Admin user ID

**Example Request**:
```http
GET /api/admins/25/
```

**Response** (200 OK):
```json
{
  "id": 25,
  "username": "newadmin",
  "email": "newadmin@molekschool.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "full_name": "Jane Smith",
  "role": "admin",
  "phone_number": "+2341234567890",
  "is_active": true,
  "age": 28,
  "sex": "female",
  "address": "456 School Ave",
  "state_of_origin": "Lagos",
  "local_govt_area": "Surulere",
  "created_at": "2024-11-20T15:30:00Z",
  "updated_at": "2024-11-20T15:30:00Z"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Error Responses**:
- 404 Not Found: Admin user does not exist
- 403 Forbidden: Insufficient permissions

---

### Update Admin

```http
PUT /api/admins/{id}/
```

**Description**: Update an existing admin user's information.

**Path Parameters**:
- `id` (integer): Admin user ID

**Request Body** (Full Update):
```json
{
  "username": "newadmin",
  "email": "updated@molekschool.com",
  "first_name": "Jane",
  "last_name": "Smith-Updated",
  "role": "admin",
  "phone_number": "+2349876543210",
  "age": 29,
  "sex": "female",
  "address": "789 New Address",
  "state_of_origin": "Lagos",
  "local_govt_area": "Ikeja"
}
```

**Partial Update** (PATCH):
```http
PATCH /api/admins/{id}/
```

**Request Body** (Partial Update):
```json
{
  "phone_number": "+2349876543210",
  "address": "789 New Address"
}
```

**Response** (200 OK):
```json
{
  "id": 25,
  "username": "newadmin",
  "email": "updated@molekschool.com",
  "first_name": "Jane",
  "last_name": "Smith-Updated",
  "full_name": "Jane Smith-Updated",
  "role": "admin",
  "phone_number": "+2349876543210",
  "is_active": true,
  "age": 29,
  "sex": "female",
  "address": "789 New Address",
  "state_of_origin": "Lagos",
  "local_govt_area": "Ikeja",
  "created_at": "2024-11-20T15:30:00Z",
  "updated_at": "2024-11-20T16:45:00Z"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- `username` cannot be changed after creation
- Password updates should use the change password endpoint
- Use PUT for full updates, PATCH for partial updates
- User cache is automatically cleared on update

---

### Delete Admin (Soft Delete)

```http
DELETE /api/admins/{id}/
```

**Description**: Deactivate an admin user (soft delete). User is set to inactive but not removed from database.

**Path Parameters**:
- `id` (integer): Admin user ID

**Response** (204 No Content):
```
No response body
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- This is a **soft delete** - user is set to `is_active=false`
- User can be reactivated by a superadmin via Django admin
- User will no longer be able to login
- User data is preserved for audit purposes

---

### Get Admin Statistics

```http
GET /api/admins/stats/
```

**Description**: Retrieve statistics about admin users in the system.

**Response** (200 OK):
```json
{
  "total_admins": 42,
  "total_superadmins": 3,
  "total": 45
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Only counts active users (is_active=true)
- Real-time statistics (not cached)
- Used for dashboard metrics

---

## 👤 PROFILE MANAGEMENT

### Get Current User Profile

```http
GET /api/users/profile/
```

**Description**: Retrieve the authenticated user's profile information.

**Response** (200 OK):
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@molekschool.com",
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",
  "role": "superadmin",
  "phone_number": "+2341234567890",
  "is_active": true,
  "age": 35,
  "sex": "male",
  "address": "123 Main St",
  "state_of_origin": "Lagos",
  "local_govt_area": "Ikeja",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-11-20T14:30:00Z"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Any authenticated user

**Notes**:
- Returns profile of currently logged-in user
- Based on JWT token payload
- Used for profile page and header display

---

### Update Current User Profile

```http
PUT /api/users/profile/
```

**Description**: Update the authenticated user's profile information.

**Request Body** (Full Update):
```json
{
  "first_name": "John",
  "last_name": "Doe-Updated",
  "phone_number": "+2349876543210",
  "age": 36,
  "sex": "male",
  "address": "456 Updated Address",
  "state_of_origin": "Lagos",
  "local_govt_area": "Victoria Island"
}
```

**Partial Update** (PATCH):
```http
PATCH /api/users/profile/
```

**Request Body** (Partial):
```json
{
  "phone_number": "+2349876543210",
  "address": "456 Updated Address"
}
```

**Response** (200 OK):
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@molekschool.com",
  "first_name": "John",
  "last_name": "Doe-Updated",
  "full_name": "John Doe-Updated",
  "phone_number": "+2349876543210",
  "age": 36,
  "sex": "male",
  "address": "456 Updated Address",
  "state_of_origin": "Lagos",
  "local_govt_area": "Victoria Island"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Any authenticated user

**Read-Only Fields**:
- `id` - Cannot be changed
- `username` - Cannot be changed
- `email` - Cannot be changed
- `full_name` - Computed from first_name + last_name
- `role` - Cannot be self-changed

**Notes**:
- Users can only update their own profile
- Password changes use separate endpoint
- Role changes require admin/superadmin permissions
- Profile cache is cleared on update

---

### Change Password

```http
POST /api/users/profile/change-password/
```

**Description**: Change the authenticated user's password.

**Request Body**:
```json
{
  "old_password": "current_password123",
  "new_password": "new_secure_password456"
}
```

**Response** (200 OK):
```json
{
  "detail": "Password changed successfully"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Any authenticated user

**Validation Rules**:
- `old_password`: Required, must match current password
- `new_password`: Required, minimum 8 characters, must pass Django password validators
- New password must be different from old password

**Error Responses**:
- 400 Bad Request: Invalid old password or weak new password
  ```json
  {
    "old_password": ["Incorrect old password"],
    "new_password": ["This password is too common"]
  }
  ```

**Notes**:
- User is automatically logged out after password change
- Must re-login with new credentials
- Password is hashed before storage (PBKDF2)

---

## 🎥 CONTENT MANAGEMENT

### List All Content

```http
GET /api/content/
```

**Description**: Retrieve a paginated list of all content items (images, videos, news).

**Query Parameters**:
- `search` (string): Search by title or description
- `content_type` (string): Filter by type (`image`, `video`, or `news`)
- `published` (boolean): Filter by published status
- `is_active` (boolean): Filter by active status
- `ordering` (string): Sort results (e.g., `-publish_date`, `title`)
- `page` (integer): Page number
- `page_size` (integer): Results per page

**Example Request**:
```http
GET /api/content/?content_type=news&published=true&page=1
```

**Response** (200 OK):
```json
{
  "count": 128,
  "next": "http://api.example.com/api/content/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "School Opening Announcement",
      "description": "The new academic term begins on January 15th...",
      "content_type": "news",
      "content_type_display": "News Article",
      "media_url": null,
      "slug": "school-opening-announcement",
      "published": true,
      "publish_date": "2024-11-15T08:00:00Z",
      "created_by": {
        "id": 1,
        "full_name": "John Doe",
        "username": "admin"
      },
      "updated_at": "2024-11-15T08:00:00Z",
      "is_active": true
    }
  ]
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Only active content (is_active=true) is returned
- Results include creator information via select_related optimization
- Supports full-text search on title and description

---

### Create Content

```http
POST /api/content/
```

**Description**: Create a new content item (image, video, or news article).

**Request Body** (multipart/form-data for images/videos):
```json
{
  "title": "New School Event",
  "description": "Annual sports day celebration...",
  "content_type": "image",
  "media": ["file"],
  "published": true
}
```

**Request Body** (JSON for news):
```json
{
  "title": "Important Announcement",
  "description": "Classes will resume on...",
  "content_type": "news",
  "published": true
}
```

**Response** (201 Created):
```json
{
  "id": 45,
  "title": "New School Event",
  "description": "Annual sports day celebration...",
  "content_type": "image",
  "content_type_display": "Image",
  "media_url": "https://res.cloudinary.com/molekschool/image/upload/v1234567890/content/media/event.jpg",
  "slug": "new-school-event",
  "published": true,
  "publish_date": "2024-11-20T15:00:00Z",
  "created_by": {
    "id": 1,
    "full_name": "John Doe",
    "username": "admin"
  },
  "updated_at": "2024-11-20T15:00:00Z",
  "is_active": true
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Content Types**:
- `image`: Requires media file (JPG, PNG, GIF, WebP)
- `video`: Requires media file (MP4, WebM, MOV)
- `news`: Media is optional

**Notes**:
- Slug is auto-generated from title
- Creator is automatically set to current user
- Media is uploaded to Cloudinary
- Maximum file size: 10MB

---

### Get Content Details

```http
GET /api/content/{id}/
```

**Description**: Retrieve detailed information about a specific content item.

**Path Parameters**:
- `id` (integer): Content item ID

**Response** (200 OK):
```json
{
  "id": 45,
  "title": "New School Event",
  "description": "Annual sports day celebration...",
  "content_type": "image",
  "content_type_display": "Image",
  "media_url": "https://res.cloudinary.com/.../event.jpg",
  "slug": "new-school-event",
  "published": true,
  "publish_date": "2024-11-20T15:00:00Z",
  "created_by": {
    "id": 1,
    "full_name": "John Doe",
    "username": "admin"
  },
  "updated_at": "2024-11-20T15:00:00Z",
  "is_active": true
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

---

### Update Content

```http
PUT /api/content/{id}/
```

**Description**: Update an existing content item.

**Path Parameters**:
- `id` (integer): Content item ID

**Request Body** (multipart/form-data):
```json
{
  "title": "Updated Event Title",
  "description": "Updated description...",
  "content_type": "image",
  "media": ["file"],
  "published": false
}
```

**Partial Update** (PATCH):
```http
PATCH /api/content/{id}/
```

**Request Body**:
```json
{
  "published": false,
  "description": "Updated description"
}
```

**Response** (200 OK):
```json
{
  "id": 45,
  "title": "Updated Event Title",
  "description": "Updated description...",
  "content_type": "image",
  "content_type_display": "Image",
  "media_url": "https://res.cloudinary.com/.../updated.jpg",
  "slug": "updated-event-title",
  "published": false,
  "publish_date": "2024-11-20T15:00:00Z",
  "created_by": {
    "id": 1,
    "full_name": "John Doe",
    "username": "admin"
  },
  "updated_at": "2024-11-20T16:30:00Z",
  "is_active": true
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Slug is regenerated if title changes
- Old media is replaced if new file is uploaded
- Use PATCH for partial updates (e.g., just toggle published)

---

### Delete Content (Soft Delete)

```http
DELETE /api/content/{id}/
```

**Description**: Deactivate a content item (soft delete).

**Path Parameters**:
- `id` (integer): Content item ID

**Response** (204 No Content):
```
No response body
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Soft delete: item is set to `is_active=false`
- Item no longer appears in public listings
- Media files remain in Cloudinary
- Can be reactivated via Django admin

---

### Get Public Content (No Auth)

```http
GET /api/content/public/
```

**Description**: Retrieve published content items for public access (no authentication required).

**Query Parameters**:
- `content_type` (string): Filter by type
- `search` (string): Search query
- `page` (integer): Page number

**Example Request**:
```http
GET /api/content/public/?content_type=news
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "title": "School Opening",
      "description": "New term begins...",
      "content_type": "news",
      "content_type_display": "News Article",
      "media_url": null,
      "slug": "school-opening",
      "published": true,
      "publish_date": "2024-11-15T08:00:00Z",
      "created_by": {
        "id": 1,
        "full_name": "John Doe",
        "username": "admin"
      },
      "updated_at": "2024-11-15T08:00:00Z",
      "is_active": true
    }
  ]
}
```

**Authentication**: None (Public endpoint)

**Permissions**: AllowAny

**Notes**:
- Only returns published content (published=true, is_active=true)
- Cached for 15 minutes for performance
- Used by public-facing website
- No authentication required

---

### Get Content Statistics

```http
GET /api/content/stats/
```

**Description**: Retrieve statistics about content items.

**Response** (200 OK):
```json
{
  "total_content": 245,
  "total_images": 120,
  "total_videos": 45,
  "total_news": 80,
  "published_content": 200
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Real-time statistics
- Only counts active content
- Used for dashboard metrics

---

## 🖼️ GALLERY MANAGEMENT

### List All Galleries

```http
GET /api/galleries/
```

**Description**: Retrieve a paginated list of all galleries.

**Query Parameters**:
- `page` (integer): Page number
- `page_size` (integer): Results per page
- `ordering` (string): Sort results

**Response** (200 OK):
```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Sports Day 2024",
      "description": "Annual sports competition...",
      "images": [
        {
          "id": 1,
          "image_url": "https://res.cloudinary.com/.../img1.jpg",
          "caption": "100m race",
          "order": 1
        },
        {
          "id": 2,
          "image_url": "https://res.cloudinary.com/.../img2.jpg",
          "caption": "Award ceremony",
          "order": 2
        }
      ],
      "created_at": "2024-11-01T10:00:00Z",
      "updated_at": "2024-11-01T10:00:00Z"
    }
  ]
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

---

### Create Gallery

```http
POST /api/galleries/
```

**Description**: Create a new gallery with multiple images.

**Request Body** (multipart/form-data):
```json
{
  "title": "Cultural Day 2024",
  "description": "Traditional dance performances...",
  "images": [
    {
      "file": ["image1"],
      "caption": "Opening ceremony",
      "order": 1
    },
    {
      "file": ["image2"],
      "caption": "Dance performance",
      "order": 2
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "id": 16,
  "title": "Cultural Day 2024",
  "description": "Traditional dance performances...",
  "images": [
    {
      "id": 45,
      "image_url": "https://res.cloudinary.com/.../cultural1.jpg",
      "caption": "Opening ceremony",
      "order": 1
    },
    {
      "id": 46,
      "image_url": "https://res.cloudinary.com/.../cultural2.jpg",
      "caption": "Dance performance",
      "order": 2
    }
  ],
  "created_at": "2024-11-20T16:00:00Z",
  "updated_at": "2024-11-20T16:00:00Z"
}
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- Supports bulk image upload
- Images are uploaded to Cloudinary
- Maximum 20 images per gallery
- Supported formats: JPG, PNG, GIF, WebP

---

### Delete Gallery

```http
DELETE /api/galleries/{id}/
```

**Description**: Permanently delete a gallery and all its images.

**Path Parameters**:
- `id` (integer): Gallery ID

**Response** (204 No Content):
```
No response body
```

**Authentication**: Required (Bearer token)

**Permissions**: Admin or SuperAdmin

**Notes**:
- This is a **hard delete** (permanent)
- All associated images are removed from Cloudinary
- Cannot be undone

---

## 📊 RESPONSE FORMATS

### Success Response

All successful responses follow this format:

**Single Object** (200 OK or 201 Created):
```json
{
  "id": 1,
  "field1": "value1",
  "field2": "value2"
}
```

**List/Collection** (200 OK):
```json
{
  "count": 100,
  "next": "http://api.example.com/endpoint/?page=2",
  "previous": null,
  "results": [
    {"..."},
    {"..."}
  ]
}
```

**No Content** (204 No Content):
```
Empty response body
```

---

## ⚠️ ERROR HANDLING

### Error Response Format

All errors follow this consistent format:

**Validation Error** (400 Bad Request):
```json
{
  "field_name": ["Error message 1", "Error message 2"],
  "another_field": ["Error message"]
}
```

**Authentication Error** (401 Unauthorized):
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**Permission Error** (403 Forbidden):
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**Not Found** (404 Not Found):
```json
{
  "detail": "Not found."
}
```

**Server Error** (500 Internal Server Error):
```json
{
  "detail": "Internal server error. Please try again later."
}
```

---

## 🔑 AUTHENTICATION

All protected endpoints require a JWT Bearer token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Token Lifecycle

1. **Login**: Obtain access + refresh tokens
2. **Use**: Send access token with each request
3. **Refresh**: Get new access token when expired (15 min)
4. **Logout**: Clear tokens from client storage

---

## 📝 NOTES

### Pagination

- Default page size: 20 items
- Max page size: 100 items
- Use `page` and `page_size` query parameters

### Filtering

- Use query parameters for filtering
- Combine multiple filters with `&`
- Example: `?role=admin&is_active=true`

### Sorting

- Use `ordering` parameter
- Prefix with `-` for descending order
- Example: `?ordering=-created_at`

### Search

- Use `search` parameter
- Searches across multiple fields
- Example: `?search=john`

---

## 🛠️ TESTING

### Using cURL

```bash
# Login
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'

# List admins
curl -X GET http://localhost:8000/api/admins/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Create content
curl -X POST http://localhost:8000/api/content/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "title=Test News" \
  -F "description=Test description" \
  -F "content_type=news" \
  -F "published=true"
```

### Using Postman

1. Import the API collection
2. Set environment variable `base_url`
3. Use {{token}} for Bearer authentication
4. Test all endpoints with sample data

---

## 🔗 RELATED DOCUMENTATION

- [Backend Structure](./BACKEND_STRUCTURE.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Frontend Structure](./FRONTEND_STRUCTURE.md)

---

**Last Updated**: November 20, 2024,  
**API Version**: 1.0  
**Base URL**: `https://molek-school-backend-production.up.railway.app`