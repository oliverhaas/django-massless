# Benchmark report: django
Config: C=50 N=10000 target=http://127.0.0.1:8002

## Framework-bound, no DB
### Root JSON Async (/)
 7490 / 10000   74.90% 2333/s 00m01s
  Reqs/sec      2318.17     246.27    3905.06
  Latency       21.59ms     3.11ms   100.96ms
  Latency Distribution
     50%    21.52ms
     75%    22.35ms
     90%    23.26ms
     99%    28.28ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
 1775 / 10000   17.75% 1474/s 00m05s
  Reqs/sec      1480.26     142.03    2718.69
  Latency       33.75ms     2.40ms    93.55ms
  Latency Distribution
     50%    33.56ms
     75%    34.47ms
     90%    35.63ms
     99%    37.99ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec      1833.56     439.44    2454.33
  Latency       27.23ms     3.25ms   102.27ms
  Latency Distribution
     50%    26.98ms
     75%    27.91ms
     90%    29.68ms
     99%    36.34ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
 2950 / 10000   29.50% 1470/s 00m04s
  Reqs/sec      1486.64     180.23    3606.33
  Latency       33.69ms     2.36ms    91.14ms
  Latency Distribution
     50%    33.63ms
     75%    34.53ms
     90%    35.43ms
     99%    38.44ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
 8590 / 10000   85.90% 1477/s
  Reqs/sec      1479.29     129.58    2562.51
  Latency       33.76ms     2.55ms   100.89ms
  Latency Distribution
     50%    33.63ms
     75%    34.33ms
     90%    35.06ms
     99%    38.55ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      1458.90     123.84    2704.93
  Latency       34.25ms     2.46ms    96.42ms
  Latency Distribution
     50%    34.16ms
     75%    35.00ms
     90%    35.84ms
     99%    39.38ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
 2950 / 10000   29.50% 1471/s 00m04s
  Reqs/sec      1475.22     137.31    2572.73
  Latency       33.86ms     2.47ms    95.70ms
  Latency Distribution
     50%    33.81ms
     75%    34.61ms
     90%    35.33ms
     99%    38.55ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec      1483.96     158.17    3581.30
  Latency       33.78ms     2.18ms    88.86ms
  Latency Distribution
     50%    33.68ms
     75%    34.45ms
     90%    35.22ms
     99%    37.01ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
 775 / 10000    7.75% 1929/s 00m04s
 8490 / 10000   84.90% 2013/s
  Reqs/sec      2017.67     541.91    4110.84
  Latency       24.82ms     3.28ms    98.62ms
  Latency Distribution
     50%    24.32ms
     75%    25.69ms
     90%    27.31ms
     99%    35.14ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
 7250 / 10000   72.50% 2125/s 00m01s
 7675 / 10000   76.75% 2125/s 00m01s
  Reqs/sec      2139.52     199.66    3346.71
  Latency       23.36ms     2.70ms    96.55ms
  Latency Distribution
     50%    23.41ms
     75%    24.08ms
     90%    24.76ms
     99%    27.71ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
 850 / 10000    8.50% 1413/s 00m06s
  Reqs/sec      1481.57     140.11    2953.57
  Latency       33.73ms     2.43ms    97.62ms
  Latency Distribution
     50%    33.52ms
     75%    34.32ms
     90%    35.16ms
     99%    38.33ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec      1470.56     139.03    2616.40
  Latency       33.96ms     2.40ms    96.08ms
  Latency Distribution
     50%    33.84ms
     75%    34.61ms
     90%    35.45ms
     99%    37.34ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
 5899 / 10000   58.99% 1470/s 00m02s
 7690 / 10000   76.90% 1474/s 00m01s
  Reqs/sec      1482.42     146.89    3192.84
  Latency       33.73ms     2.30ms    93.00ms
  Latency Distribution
     50%    33.58ms
     75%    34.23ms
     90%    35.15ms
     99%    37.68ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec      1486.62     137.79    3122.39
  Latency       33.63ms     2.22ms    92.88ms
  Latency Distribution
     50%    33.56ms
     75%    34.17ms
     90%    34.88ms
     99%    36.40ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
 4975 / 10000   49.75% 1458/s 00m03s
 9099 / 10000   90.99% 1463/s
 9390 / 10000   93.90% 1463/s
  Reqs/sec      1472.37     160.30    3449.85
  Latency       34.00ms     2.33ms    93.88ms
  Latency Distribution
     50%    33.85ms
     75%    34.64ms
     90%    35.60ms
     99%    37.59ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
 7090 / 10000   70.90% 1473/s 00m01s
 8299 / 10000   82.99% 1478/s 00m01s
  Reqs/sec      1480.22     129.74    2601.62
  Latency       33.75ms     2.36ms    94.33ms
  Latency Distribution
     50%    33.64ms
     75%    34.29ms
     90%    34.98ms
     99%    37.38ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
 4775 / 10000   47.75% 1488/s 00m03s
  Reqs/sec      1498.75     134.12    2891.96
  Latency       33.34ms     2.33ms    92.73ms
  Latency Distribution
     50%    33.29ms
     75%    33.91ms
     90%    34.54ms
     99%    36.45ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec      1476.26     163.81    3526.26
  Latency       33.91ms     2.28ms    95.53ms
  Latency Distribution
     50%    33.79ms
     75%    34.48ms
     90%    35.16ms
     99%    36.67ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
 2950 / 10000   29.50% 1471/s 00m04s
  Reqs/sec      1471.38     138.78    2565.85
  Latency       33.95ms     2.73ms    95.73ms
  Latency Distribution
     50%    33.63ms
     75%    34.34ms
     90%    35.21ms
     99%    43.41ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
 850 / 10000    8.50% 1413/s 00m06s
  Reqs/sec      1481.66     139.14    2853.61
  Latency       33.73ms     2.15ms    92.67ms
  Latency Distribution
     50%    33.68ms
     75%    34.32ms
     90%    34.93ms
     99%    36.29ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
 4590 / 10000   45.90% 1430/s 00m03s
 6075 / 10000   60.75% 1443/s 00m02s
  Reqs/sec      1455.32     170.78    3494.45
  Latency       34.40ms     2.64ms    98.68ms
  Latency Distribution
     50%    34.06ms
     75%    34.97ms
     90%    36.27ms
     99%    41.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec      1470.42     205.30    4626.32
  Latency       34.17ms     2.28ms    91.53ms
  Latency Distribution
     50%    33.98ms
     75%    34.81ms
     90%    35.72ms
     99%    38.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
 3850 / 10000   38.50% 1476/s 00m04s
 5950 / 10000   59.50% 1483/s 00m02s
  Reqs/sec      1488.26     120.99    2616.31
  Latency       33.56ms     2.30ms    94.54ms
  Latency Distribution
     50%    33.46ms
     75%    34.14ms
     90%    34.82ms
     99%    36.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
 1475 / 10000   14.75% 1471/s 00m05s
 7390 / 10000   73.90% 1474/s 00m01s
 7675 / 10000   76.75% 1472/s 00m01s
  Reqs/sec      1471.20     131.20    2552.82
  Latency       33.96ms     2.34ms    95.24ms
  Latency Distribution
     50%    33.85ms
     75%    34.67ms
     90%    35.45ms
     99%    37.27ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
 1450 / 10000   14.50% 1445/s 00m05s
  Reqs/sec      1490.35     200.84    4454.54
  Latency       33.68ms     2.45ms    97.28ms
  Latency Distribution
     50%    33.49ms
     75%    34.20ms
     90%    34.99ms
     99%    37.72ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
 4750 / 10000   47.50% 1478/s 00m03s
 5050 / 10000   50.50% 1479/s 00m03s
 8650 / 10000   86.50% 1486/s
  Reqs/sec      1498.73     189.38    4170.67
  Latency       33.48ms     2.32ms    96.42ms
  Latency Distribution
     50%    33.36ms
     75%    34.02ms
     90%    34.79ms
     99%    36.42ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
 2999 / 10000   29.99% 1496/s 00m04s
 3299 / 10000   32.99% 1495/s 00m04s
 3599 / 10000   35.99% 1495/s 00m04s
  Reqs/sec      1505.17     146.27    3317.05
  Latency       33.23ms     2.12ms    91.65ms
  Latency Distribution
     50%    33.15ms
     75%    33.75ms
     90%    34.36ms
     99%    35.57ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
 3575 / 10000   35.75% 1485/s 00m04s
 5390 / 10000   53.90% 1493/s 00m03s
 7190 / 10000   71.90% 1494/s 00m01s
  Reqs/sec      1496.03     156.37    3270.01
  Latency       33.43ms     2.51ms    96.65ms
  Latency Distribution
     50%    33.27ms
     75%    33.96ms
     90%    34.51ms
     99%    37.89ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
 7075 / 10000   70.75% 1469/s 00m01s
 7675 / 10000   76.75% 1471/s 00m01s
  Reqs/sec      1481.24     140.65    2999.82
  Latency       33.74ms     2.37ms    95.45ms
  Latency Distribution
     50%    33.60ms
     75%    34.33ms
     90%    35.08ms
     99%    36.81ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec      1493.27     126.11    2731.10
  Latency       33.45ms     2.22ms    91.90ms
  Latency Distribution
     50%    33.36ms
     75%    33.92ms
     90%    34.62ms
     99%    37.22ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
 2675 / 10000   26.75% 1481/s 00m04s
 5699 / 10000   56.99% 1495/s 00m02s
  Reqs/sec      1515.32     221.20    4610.31
  Latency       33.17ms     2.25ms    93.15ms
  Latency Distribution
     50%    33.08ms
     75%    33.66ms
     90%    34.24ms
     99%    35.87ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
