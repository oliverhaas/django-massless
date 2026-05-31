# Benchmark report: django
Config: C=50 N=10000 target=http://127.0.0.1:8002

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec      4387.16     300.56    5464.02
  Latency       11.38ms     0.91ms    28.48ms
  Latency Distribution
     50%    11.11ms
     75%    11.93ms
     90%    12.42ms
     99%    14.02ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
 4050 / 10000   40.50% 2888/s 00m02s
  Reqs/sec      2874.63     210.63    3905.65
  Latency       17.37ms     1.09ms    33.10ms
  Latency Distribution
     50%    17.25ms
     75%    17.77ms
     90%    18.44ms
     99%    20.91ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
 4999 / 10000   49.99% 3562/s 00m01s
  Reqs/sec      3580.11     244.59    4620.67
  Latency       13.95ms     1.04ms    33.05ms
  Latency Distribution
     50%    13.96ms
     75%    14.35ms
     90%    14.77ms
     99%    17.87ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec      2778.52     226.81    3788.61
  Latency       17.97ms     1.34ms    33.75ms
  Latency Distribution
     50%    17.88ms
     75%    18.40ms
     90%    19.22ms
     99%    23.48ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec      2747.25     243.11    5078.71
  Latency       18.23ms     1.17ms    32.31ms
  Latency Distribution
     50%    18.16ms
     75%    18.82ms
     90%    19.48ms
     99%    22.80ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      2786.58     224.17    4083.62
  Latency       17.94ms     1.19ms    34.15ms
  Latency Distribution
     50%    17.89ms
     75%    18.40ms
     90%    19.16ms
     99%    21.54ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
 1650 / 10000   16.50% 2737/s 00m03s
 4999 / 10000   49.99% 2769/s 00m01s
  Reqs/sec      2777.97     372.81    7021.63
  Latency       18.10ms     1.32ms    34.28ms
  Latency Distribution
     50%    18.05ms
     75%    18.66ms
     90%    19.32ms
     99%    21.41ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
 3390 / 10000   33.90% 2816/s 00m02s
  Reqs/sec      2819.45     342.96    6297.27
  Latency       17.80ms     1.47ms    34.85ms
  Latency Distribution
     50%    17.68ms
     75%    18.36ms
     90%    19.15ms
     99%    24.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec      4042.42     252.21    5442.70
  Latency       12.36ms   688.74us    27.48ms
  Latency Distribution
     50%    12.32ms
     75%    12.61ms
     90%    13.07ms
     99%    14.01ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec      4004.93     235.09    4681.66
  Latency       12.46ms     0.92ms    24.01ms
  Latency Distribution
     50%    12.41ms
     75%    12.93ms
     90%    13.42ms
     99%    16.09ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
 2199 / 10000   21.99% 2742/s 00m02s
  Reqs/sec      2780.13     258.43    5126.42
  Latency       18.01ms     1.26ms    33.80ms
  Latency Distribution
     50%    17.98ms
     75%    18.49ms
     90%    19.23ms
     99%    21.79ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec      2648.89     296.63    5185.21
  Latency       18.91ms     1.50ms    33.02ms
  Latency Distribution
     50%    18.75ms
     75%    19.82ms
     90%    20.95ms
     99%    23.57ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
  Reqs/sec      2693.62     236.15    4231.91
  Latency       18.59ms     1.34ms    36.25ms
  Latency Distribution
     50%    18.46ms
     75%    19.38ms
     90%    20.20ms
     99%    22.20ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec      2731.95     209.95    3374.28
  Latency       18.28ms     2.50ms    40.43ms
  Latency Distribution
     50%    18.03ms
     75%    20.99ms
     90%    22.08ms
     99%    25.00ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
 5875 / 10000   58.75% 2665/s 00m01s
  Reqs/sec      2709.19     292.02    5614.54
  Latency       18.51ms     1.68ms    35.03ms
  Latency Distribution
     50%    18.40ms
     75%    19.36ms
     90%    20.25ms
     99%    23.68ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec      2815.33     295.39    5600.51
  Latency       17.81ms     1.20ms    35.86ms
  Latency Distribution
     50%    17.82ms
     75%    18.29ms
     90%    19.02ms
     99%    21.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec      2805.90     243.78    4811.14
  Latency       17.83ms     1.15ms    34.10ms
  Latency Distribution
     50%    17.85ms
     75%    18.32ms
     90%    18.98ms
     99%    21.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
 9899 / 10000   98.99% 2744/s
  Reqs/sec      2754.15     210.36    4172.88
  Latency       18.15ms     1.24ms    33.74ms
  Latency Distribution
     50%    18.13ms
     75%    18.58ms
     90%    19.36ms
     99%    22.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
 4490 / 10000   44.90% 2801/s 00m01s
  Reqs/sec      2801.17     236.24    4261.34
  Latency       17.84ms     1.40ms    33.16ms
  Latency Distribution
     50%    17.70ms
     75%    18.75ms
     90%    19.36ms
     99%    22.78ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
 9275 / 10000   92.75% 2721/s
  Reqs/sec      2762.41     493.56    8693.36
  Latency       18.28ms     1.43ms    35.00ms
  Latency Distribution
     50%    18.21ms
     75%    18.84ms
     90%    19.68ms
     99%    23.76ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
 4375 / 10000   43.75% 2728/s 00m02s
  Reqs/sec      2750.90     218.64    3876.85
  Latency       18.18ms     1.23ms    34.02ms
  Latency Distribution
     50%    18.16ms
     75%    18.70ms
     90%    19.42ms
     99%    22.51ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
 7275 / 10000   72.75% 2792/s
  Reqs/sec      2807.33     242.18    4824.58
  Latency       17.83ms     1.15ms    33.92ms
  Latency Distribution
     50%    17.84ms
     75%    18.33ms
     90%    18.97ms
     99%    21.34ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec      2752.08     231.94    3815.09
  Latency       18.18ms     1.27ms    37.51ms
  Latency Distribution
     50%    18.15ms
     75%    18.80ms
     90%    19.46ms
     99%    21.43ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec      2783.36     216.45    4213.89
  Latency       17.95ms     1.19ms    34.21ms
  Latency Distribution
     50%    17.97ms
     75%    18.46ms
     90%    19.14ms
     99%    21.30ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec      2778.81     197.45    3782.50
  Latency       17.97ms     1.41ms    31.29ms
  Latency Distribution
     50%    17.82ms
     75%    18.87ms
     90%    19.62ms
     99%    22.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
 3850 / 10000   38.50% 2746/s 00m02s
  Reqs/sec      2775.02     224.30    4219.92
  Latency       18.01ms     1.88ms    38.71ms
  Latency Distribution
     50%    17.90ms
     75%    20.09ms
     90%    20.60ms
     99%    22.87ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
 3299 / 10000   32.99% 2742/s 00m02s
  Reqs/sec      2797.45     311.47    5935.69
  Latency       17.92ms     1.22ms    34.23ms
  Latency Distribution
     50%    17.93ms
     75%    18.49ms
     90%    19.25ms
     99%    21.59ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec      2815.26     275.00    5101.46
  Latency       17.80ms     1.30ms    35.36ms
  Latency Distribution
     50%    17.70ms
     75%    18.70ms
     90%    19.27ms
     99%    21.51ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
 5090 / 10000   50.90% 2823/s 00m01s
  Reqs/sec      2862.71     398.40    7281.95
  Latency       17.59ms     1.07ms    32.04ms
  Latency Distribution
     50%    17.62ms
     75%    18.08ms
     90%    18.62ms
     99%    21.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec      2811.50     285.95    5482.13
  Latency       17.82ms     1.41ms    33.15ms
  Latency Distribution
     50%    17.70ms
     75%    18.63ms
     90%    19.20ms
     99%    25.45ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
 2790 / 10000   27.90% 2784/s 00m02s
  Reqs/sec      2834.16     316.43    6155.88
  Latency       17.71ms     1.10ms    31.77ms
  Latency Distribution
     50%    17.77ms
     75%    18.25ms
     90%    18.70ms
     99%    20.85ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
