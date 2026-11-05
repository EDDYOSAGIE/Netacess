import requests, uuid

API_KEY = "esp_9c33ca8a-3568-411e-b8d5-ec3dca272faf"
WALLET = "0x49e99dd6ec7b413867513052053161c3682d5506"

r = requests.post(
    "https://api.espees.org/v2/payment/product",
    headers={"Content-Type": "application/json", "x-api-key": API_KEY},
    json={
        "product_sku": f"TEST-{uuid.uuid4().hex[:12]}",
        "narration": "Netacess test",
        "price": 0.1,
        "merchant_wallet": WALLET,
        "success_url": "http://localhost:3000/payment/success",
        "fail_url": "http://localhost:3000/payment/failure",
    },
    timeout=15,
)
print(r.status_code, r.text)
print(repr(API_KEY), len(API_KEY))
print(r.headers.get("x-amzn-ErrorType"))