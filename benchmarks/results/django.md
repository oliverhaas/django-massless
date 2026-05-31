# Benchmark report: django
Config: C=50 N=10000 target=http://127.0.0.1:8002

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec      2285.06     316.94    5433.46
  Latency       21.98ms     2.87ms    97.34ms
  Latency Distribution
     50%    21.98ms
     75%    22.86ms
     90%    23.56ms
     99%    27.77ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec      1467.21     201.26    3433.73
  Latency       34.12ms     2.25ms    91.28ms
  Latency Distribution
     50%    33.91ms
     75%    34.82ms
     90%    35.83ms
     99%    40.27ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
 3190 / 10000   31.90% 1765/s 00m03s
  Reqs/sec      1729.57     600.54    4023.49
  Latency       28.97ms     3.85ms   103.08ms
  Latency Distribution
     50%    28.26ms
     75%    30.15ms
     90%    32.83ms
     99%    40.07ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
 7399 / 10000   73.99% 1475/s 00m01s
  Reqs/sec      1490.29     170.88    3716.63
  Latency       33.61ms     2.61ms    96.85ms
  Latency Distribution
     50%    33.41ms
     75%    34.35ms
     90%    35.37ms
     99%    40.55ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
 850 / 10000    8.50% 1411/s 00m06s
  Reqs/sec      1463.42     156.19    3499.07
  Latency       34.21ms     2.42ms    94.56ms
  Latency Distribution
     50%    34.06ms
     75%    34.86ms
     90%    35.64ms
     99%    40.24ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      1486.09     134.23    2421.96
  Latency       33.67ms     2.34ms    95.23ms
  Latency Distribution
     50%    33.57ms
     75%    34.29ms
     90%    35.00ms
     99%    38.17ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec      1426.60     220.97    4475.18
  Latency       35.18ms     2.74ms    96.56ms
  Latency Distribution
     50%    34.68ms
     75%    36.23ms
     90%    37.91ms
     99%    42.21ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec      1451.12     135.74    2698.02
  Latency       34.44ms     2.50ms    98.56ms
  Latency Distribution
     50%    34.19ms
     75%    35.19ms
     90%    36.34ms
     99%    38.63ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec      2152.81     240.02    4957.68
  Latency       23.30ms     2.61ms    92.36ms
  Latency Distribution
     50%    23.32ms
     75%    23.99ms
     90%    24.49ms
     99%    28.56ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec      2179.96     446.55    8385.81
  Latency       23.18ms     2.61ms    92.13ms
  Latency Distribution
     50%    23.21ms
     75%    23.90ms
     90%    24.48ms
     99%    27.65ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
 3250 / 10000   32.50% 1473/s 00m04s
 9650 / 10000   96.50% 1457/s
  Reqs/sec      1464.04     173.13    3249.56
  Latency       34.19ms     2.39ms    91.67ms
  Latency Distribution
     50%    33.92ms
     75%    34.95ms
     90%    36.04ms
     99%    39.43ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
 2590 / 10000   25.90% 1434/s 00m05s
 2890 / 10000   28.90% 1440/s 00m04s
 4699 / 10000   46.99% 1463/s 00m03s
 7975 / 10000   79.75% 1472/s 00m01s
  Reqs/sec      1490.20     275.01    6049.62
  Latency       33.78ms     2.47ms    96.68ms
  Latency Distribution
     50%    33.53ms
     75%    34.29ms
     90%    35.30ms
     99%    38.96ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
 3250 / 10000   32.50% 1472/s 00m04s
 5590 / 10000   55.90% 1466/s 00m03s
 5890 / 10000   58.90% 1468/s 00m02s
 6775 / 10000   67.75% 1468/s 00m02s
 8275 / 10000   82.75% 1473/s 00m01s
 8875 / 10000   88.75% 1475/s
  Reqs/sec      1491.06     230.89    5197.44
  Latency       33.69ms     2.26ms    92.06ms
  Latency Distribution
     50%    33.57ms
     75%    34.31ms
     90%    35.16ms
     99%    36.37ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec      1478.93     212.07    4592.77
  Latency       33.97ms     2.43ms    95.79ms
  Latency Distribution
     50%    33.80ms
     75%    34.50ms
     90%    35.40ms
     99%    39.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
 3399 / 10000   33.99% 1411/s 00m04s
  Reqs/sec      1636.30    3171.65   60059.26
  Latency       34.07ms     2.70ms    94.57ms
  Latency Distribution
     50%    33.68ms
     75%    34.95ms
     90%    36.11ms
     99%    40.35ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
 8550 / 10000   85.50% 1469/s
  Reqs/sec      1482.01     144.78    3038.35
  Latency       33.74ms     2.42ms   100.89ms
  Latency Distribution
     50%    33.60ms
     75%    34.34ms
     90%    35.04ms
     99%    37.02ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
 3599 / 10000   35.99% 1495/s 00m04s
  Reqs/sec      1508.01     219.43    4864.62
  Latency       33.29ms     2.33ms    92.86ms
  Latency Distribution
     50%    33.10ms
     75%    33.74ms
     90%    34.58ms
     99%    37.91ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
 2650 / 10000   26.50% 1469/s 00m05s
  Reqs/sec      1495.76     138.04    3126.58
  Latency       33.43ms     2.36ms    96.35ms
  Latency Distribution
     50%    33.26ms
     75%    33.84ms
     90%    34.54ms
     99%    37.69ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
 7675 / 10000   76.75% 1417/s 00m01s
  Reqs/sec      1432.98     188.36    3419.21
  Latency       34.92ms     3.45ms    93.08ms
  Latency Distribution
     50%    34.14ms
     75%    35.23ms
     90%    37.25ms
     99%    49.60ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec      1494.08     280.09    6105.44
  Latency       33.68ms     2.51ms    92.45ms
  Latency Distribution
     50%    33.34ms
     75%    34.19ms
     90%    35.31ms
     99%    39.85ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
 4290 / 10000   42.90% 1425/s 00m04s
 5175 / 10000   51.75% 1433/s 00m03s
 5775 / 10000   57.75% 1439/s 00m02s
  Reqs/sec      1448.61     155.72    3062.08
  Latency       34.52ms     2.67ms    95.03ms
  Latency Distribution
     50%    34.23ms
     75%    35.02ms
     90%    36.20ms
     99%    44.30ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec      1499.30     131.34    2806.22
  Latency       33.34ms     2.24ms    92.92ms
  Latency Distribution
     50%    33.23ms
     75%    33.90ms
     90%    34.57ms
     99%    36.28ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec      1475.33     137.34    2643.19
  Latency       33.86ms     2.66ms    93.05ms
  Latency Distribution
     50%    33.40ms
     75%    34.17ms
     90%    35.99ms
     99%    41.33ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec      1511.79     149.68    3353.99
  Latency       33.11ms     2.24ms    90.28ms
  Latency Distribution
     50%    32.96ms
     75%    33.63ms
     90%    34.45ms
     99%    38.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
 9399 / 10000   93.99% 1512/s
  Reqs/sec      1515.66     139.23    2714.59
  Latency       32.97ms     2.17ms    92.40ms
  Latency Distribution
     50%    32.86ms
     75%    33.41ms
     90%    33.94ms
     99%    35.52ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
 6175 / 10000   61.75% 1465/s 00m02s
  Reqs/sec      1478.91     146.09    3143.81
  Latency       33.81ms     2.33ms    90.80ms
  Latency Distribution
     50%    33.63ms
     75%    34.38ms
     90%    35.36ms
     99%    38.83ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
 5399 / 10000   53.99% 1495/s 00m03s
  Reqs/sec      1505.81     145.07    3243.18
  Latency       33.22ms     2.25ms    91.03ms
  Latency Distribution
     50%    33.02ms
     75%    33.66ms
     90%    34.64ms
     99%    37.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
 575 / 10000    5.75% 1432/s 00m06s
  Reqs/sec      1544.98     729.72   14641.72
  Latency       33.16ms     2.22ms    91.59ms
  Latency Distribution
     50%    33.03ms
     75%    33.58ms
     90%    34.21ms
     99%    37.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
 5999 / 10000   59.99% 1495/s 00m02s
  Reqs/sec      1496.68     142.90    3085.05
  Latency       33.42ms     2.31ms    96.18ms
  Latency Distribution
     50%    33.25ms
     75%    34.05ms
     90%    34.77ms
     99%    36.20ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
 4299 / 10000   42.99% 1429/s 00m03s
  Reqs/sec      1437.99     146.43    2822.26
  Latency       34.75ms     2.88ms    99.98ms
  Latency Distribution
     50%    34.46ms
     75%    35.41ms
     90%    36.40ms
     99%    41.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec      1489.91     155.99    3504.70
  Latency       33.60ms     2.48ms    97.64ms
  Latency Distribution
     50%    33.41ms
     75%    34.10ms
     90%    34.94ms
     99%    37.71ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
