# Benchmark report: django
Config: C=50 N=10000 target=http://127.0.0.1:8002

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec      2308.48     341.88    4201.48
  Latency       21.65ms     3.07ms    93.98ms
  Latency Distribution
     50%    21.18ms
     75%    22.46ms
     90%    23.88ms
     99%    30.86ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
 590 / 10000    5.90% 1471/s 00m06s
  Reqs/sec      1501.77     256.06    5360.91
  Latency       33.48ms     2.44ms    89.63ms
  Latency Distribution
     50%    33.19ms
     75%    34.13ms
     90%    35.61ms
     99%    40.25ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
 2975 / 10000   29.75% 1851/s 00m03s
 8090 / 10000   80.90% 1832/s 00m01s
  Reqs/sec      1838.88     473.91    3253.48
  Latency       27.15ms     3.35ms   105.45ms
  Latency Distribution
     50%    26.74ms
     75%    27.96ms
     90%    29.91ms
     99%    35.93ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
 9850 / 10000   98.50% 1487/s
  Reqs/sec      1498.12     202.85    4499.24
  Latency       33.49ms     2.52ms    94.12ms
  Latency Distribution
     50%    33.30ms
     75%    34.00ms
     90%    34.85ms
     99%    38.54ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
 2975 / 10000   29.75% 1484/s 00m04s
 4475 / 10000   44.75% 1487/s 00m03s
  Reqs/sec      1496.58     174.61    3723.51
  Latency       33.48ms     2.24ms    92.67ms
  Latency Distribution
     50%    33.36ms
     75%    34.06ms
     90%    34.77ms
     99%    36.44ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
 4175 / 10000   41.75% 1487/s 00m03s
 4775 / 10000   47.75% 1488/s 00m03s
 8090 / 10000   80.90% 1494/s 00m01s
 8390 / 10000   83.90% 1494/s 00m01s
 9875 / 10000   98.75% 1492/s
  Reqs/sec      1498.80     169.88    3502.16
  Latency       33.40ms     2.40ms    95.75ms
  Latency Distribution
     50%    33.33ms
     75%    34.05ms
     90%    34.77ms
     99%    38.34ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
 2999 / 10000   29.99% 1494/s 00m04s
  Reqs/sec      1501.86     167.66    3595.97
  Latency       33.32ms     2.35ms    93.37ms
  Latency Distribution
     50%    33.13ms
     75%    33.80ms
     90%    34.61ms
     99%    38.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec      1483.99     162.56    3322.14
  Latency       33.71ms     2.49ms    94.22ms
  Latency Distribution
     50%    33.36ms
     75%    34.16ms
     90%    35.41ms
     99%    39.53ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec      2168.71     185.94    3510.04
  Latency       23.05ms     2.48ms    90.18ms
  Latency Distribution
     50%    23.11ms
     75%    23.72ms
     90%    24.26ms
     99%    26.43ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
 399 / 10000    3.99% 1987/s 00m04s
  Reqs/sec      2030.06     495.95    2936.95
  Latency       24.58ms     3.19ms    93.51ms
  Latency Distribution
     50%    24.10ms
     75%    25.29ms
     90%    27.02ms
     99%    35.05ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec      1493.98     125.42    2692.57
  Latency       33.44ms     2.25ms    93.21ms
  Latency Distribution
     50%    33.40ms
     75%    34.05ms
     90%    34.66ms
     99%    36.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
 8599 / 10000   85.99% 1478/s
 9790 / 10000   97.90% 1479/s
  Reqs/sec      1487.89     164.22    3542.29
  Latency       33.68ms     2.35ms    95.85ms
  Latency Distribution
     50%    33.58ms
     75%    34.34ms
     90%    35.16ms
     99%    37.01ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
 3550 / 10000   35.50% 1475/s 00m04s
  Reqs/sec      1510.05     240.04    5254.40
  Latency       33.28ms     2.21ms    92.82ms
  Latency Distribution
     50%    33.16ms
     75%    33.79ms
     90%    34.59ms
     99%    36.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
 5050 / 10000   50.50% 1480/s 00m03s
  Reqs/sec      1488.40     147.17    3380.10
  Latency       33.62ms     2.35ms    95.82ms
  Latency Distribution
     50%    33.43ms
     75%    34.12ms
     90%    34.90ms
     99%    37.57ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
 2950 / 10000   29.50% 1471/s 00m04s
  Reqs/sec      1484.88     201.45    4272.68
  Latency       33.79ms     2.54ms    94.24ms
  Latency Distribution
     50%    33.57ms
     75%    34.38ms
     90%    35.31ms
     99%    40.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec      1487.79     298.56    6547.06
  Latency       33.88ms     2.40ms    95.18ms
  Latency Distribution
     50%    33.66ms
     75%    34.50ms
     90%    35.54ms
     99%    38.37ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec      1495.64     144.65    3099.84
  Latency       33.44ms     2.34ms    92.80ms
  Latency Distribution
     50%    33.41ms
     75%    34.05ms
     90%    34.68ms
     99%    36.89ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
 4050 / 10000   40.50% 1442/s 00m04s
 6099 / 10000   60.99% 1448/s 00m02s
 6999 / 10000   69.99% 1454/s 00m02s
 7299 / 10000   72.99% 1455/s 00m01s
  Reqs/sec      1460.80     143.50    2860.36
  Latency       34.22ms     2.50ms    98.32ms
  Latency Distribution
     50%    34.05ms
     75%    34.74ms
     90%    35.43ms
     99%    39.60ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec      1468.49     134.29    2530.55
  Latency       34.06ms     2.36ms    97.99ms
  Latency Distribution
     50%    34.01ms
     75%    34.74ms
     90%    35.38ms
     99%    36.54ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
 5575 / 10000   55.75% 1463/s 00m03s
 6150 / 10000   61.50% 1460/s 00m02s
  Reqs/sec      1470.60     144.36    3223.98
  Latency       34.02ms     2.33ms    94.25ms
  Latency Distribution
     50%    33.89ms
     75%    34.59ms
     90%    35.30ms
     99%    37.42ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
 3750 / 10000   37.50% 1438/s 00m04s
 7590 / 10000   75.90% 1455/s 00m01s
  Reqs/sec      1495.36     643.07   13147.82
  Latency       34.16ms     2.37ms    95.20ms
  Latency Distribution
     50%    34.00ms
     75%    34.71ms
     90%    35.61ms
     99%    39.13ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec      1483.53     160.99    3130.57
  Latency       33.71ms     2.71ms    90.66ms
  Latency Distribution
     50%    33.41ms
     75%    34.10ms
     90%    34.94ms
     99%    42.19ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec      1496.64     184.17    4117.00
  Latency       33.50ms     2.40ms    96.06ms
  Latency Distribution
     50%    33.38ms
     75%    34.08ms
     90%    34.79ms
     99%    36.98ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
 2650 / 10000   26.50% 1468/s 00m05s
  Reqs/sec      1492.91     180.42    3876.91
  Latency       33.58ms     2.30ms    93.78ms
  Latency Distribution
     50%    33.43ms
     75%    34.13ms
     90%    34.94ms
     99%    37.35ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
 6850 / 10000   68.50% 1485/s 00m02s
  Reqs/sec      1498.45     156.97    3518.02
  Latency       33.42ms     2.24ms    94.66ms
  Latency Distribution
     50%    33.36ms
     75%    33.90ms
     90%    34.37ms
     99%    35.73ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
 1799 / 10000   17.99% 1494/s 00m05s
 7790 / 10000   77.90% 1493/s 00m01s
  Reqs/sec      1499.70     165.78    3723.70
  Latency       33.40ms     2.22ms    91.88ms
  Latency Distribution
     50%    33.34ms
     75%    33.98ms
     90%    34.66ms
     99%    36.37ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
 7999 / 10000   79.99% 1476/s 00m01s
  Reqs/sec      1479.66     151.65    3345.84
  Latency       33.81ms     2.29ms    96.27ms
  Latency Distribution
     50%    33.74ms
     75%    34.38ms
     90%    35.02ms
     99%    36.39ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
 1750 / 10000   17.50% 1454/s 00m05s
 7675 / 10000   76.75% 1417/s 00m01s
  Reqs/sec      1419.88     183.41    3322.06
  Latency       35.23ms     3.00ms    92.84ms
  Latency Distribution
     50%    34.63ms
     75%    36.31ms
     90%    38.23ms
     99%    45.63ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec      1436.77     252.15    5291.67
  Latency       34.98ms     2.82ms   105.40ms
  Latency Distribution
     50%    34.77ms
     75%    35.68ms
     90%    36.93ms
     99%    40.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
 9190 / 10000   91.90% 1431/s
  Reqs/sec      1441.87     201.78    3829.76
  Latency       34.78ms     3.07ms    95.49ms
  Latency Distribution
     50%    34.27ms
     75%    35.37ms
     90%    36.96ms
     99%    47.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
 4490 / 10000   44.90% 1399/s 00m03s
 9750 / 10000   97.50% 1430/s
  Reqs/sec      1436.12     162.69    2990.09
  Latency       34.82ms     2.81ms    96.83ms
  Latency Distribution
     50%    34.41ms
     75%    35.54ms
     90%    36.84ms
     99%    42.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
