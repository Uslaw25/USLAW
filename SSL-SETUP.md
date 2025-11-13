# SSL Certificate Setup for app.uslawai.com

## Production Deployment Instructions

### 1. SSL Certificate Requirements

Before deploying to production, you need to obtain SSL certificates for `app.uslawai.com`. 

#### Option A: Let's Encrypt (Free)
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificates
sudo certbot certonly --standalone -d app.uslawai.com

# Certificates will be saved to:
# /etc/letsencrypt/live/app.uslawai.com/fullchain.pem
# /etc/letsencrypt/live/app.uslawai.com/privkey.pem
```

#### Option B: Custom SSL Certificates
Place your SSL certificates in the `ssl/` directory:
```
ssl/
├── app.uslawai.com.pem  (certificate + intermediate chain)
└── app.uslawai.com.key  (private key)
```

### 2. SSL Directory Setup

Create the SSL directory structure:
```bash
mkdir -p ssl
chmod 700 ssl
```

Copy your certificates:
```bash
# For Let's Encrypt certificates:
sudo cp /etc/letsencrypt/live/app.uslawai.com/fullchain.pem ssl/app.uslawai.com.pem
sudo cp /etc/letsencrypt/live/app.uslawai.com/privkey.pem ssl/app.uslawai.com.key

# Set proper permissions
chmod 644 ssl/app.uslawai.com.pem
chmod 600 ssl/app.uslawai.com.key
```

### 3. DNS Configuration

Ensure your DNS points to your server:
```
app.uslawai.com.  A  YOUR_SERVER_IP
```

### 4. Production Deployment

```bash
# Start production services
docker-compose up -d --build

# Verify services are running
docker-compose ps

# Check logs if needed
docker-compose logs gateway
docker-compose logs backend
docker-compose logs frontend
```

### 5. Domain Access

After deployment:
- **React App**: https://app.uslawai.com/app
- **Chainlit Chat**: https://app.uslawai.com/chat
- **API Docs**: https://app.uslawai.com/docs

### 6. Security Features Enabled

- ✅ HTTPS redirect (HTTP → HTTPS)
- ✅ HSTS (Strict Transport Security)
- ✅ Modern SSL/TLS configuration
- ✅ Security headers (X-Frame-Options, X-Content-Type-Options)
- ✅ HTTP/2 support

### 7. Environment Variables

Ensure these environment variables are set for production:
```bash
GOOGLE_CLIENT_ID=your_production_google_client_id
CHAINLIT_AUTH_SECRET=your_production_auth_secret
AWS_S3_BUCKET_NAME=your_production_bucket
AWS_ACCESS_KEY_ID=your_production_access_key
AWS_SECRET_ACCESS_KEY=your_production_secret_key
```

### 8. Certificate Renewal (Let's Encrypt)

Set up automatic renewal:
```bash
# Add to crontab
0 12 * * * /usr/bin/certbot renew --quiet --deploy-hook "docker-compose restart gateway"
```