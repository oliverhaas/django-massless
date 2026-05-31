# Benchmark report: bolt
Config: C=50 N=10000 target=http://127.0.0.1:8001

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     38367.48    1557.03   40468.76
  Latency        1.30ms   656.68us    18.96ms
  Latency Distribution
     50%     1.29ms
     75%     1.31ms
     90%     1.37ms
     99%     1.90ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     42136.87    1725.73   43517.37
  Latency        1.18ms    65.56us     2.74ms
  Latency Distribution
     50%     1.16ms
     75%     1.19ms
     90%     1.24ms
     99%     1.53ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     27257.54    1105.97   28352.65
  Latency        1.82ms    66.99us     3.80ms
  Latency Distribution
     50%     1.81ms
     75%     1.87ms
     90%     1.91ms
     99%     2.12ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     27919.84     944.53   29059.99
  Latency        1.78ms   102.12us     3.65ms
  Latency Distribution
     50%     1.76ms
     75%     1.82ms
     90%     1.88ms
     99%     2.18ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     36289.91    2045.13   38305.95
  Latency        1.37ms    67.67us     3.24ms
  Latency Distribution
     50%     1.34ms
     75%     1.43ms
     90%     1.45ms
     99%     1.79ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      8582.11     536.21    8959.98
  Latency        5.81ms   434.85us    12.16ms
  Latency Distribution
     50%     5.71ms
     75%     5.79ms
     90%     6.03ms
     99%     8.23ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec      1897.26      75.59    2038.22
  Latency       26.29ms     1.22ms    33.57ms
  Latency Distribution
     50%    26.11ms
     75%    26.51ms
     90%    27.34ms
     99%    30.30ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1mb JSON (/1m-json)
 5450 / 10000   54.50% 937/s 00m04s
  Reqs/sec       942.18      24.69    1003.86
  Latency       52.94ms     2.10ms    62.39ms
  Latency Distribution
     50%    52.80ms
     75%    53.23ms
     90%    54.12ms
     99%    56.03ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     31729.73     559.29   32351.69
  Latency        1.57ms    68.47us     3.85ms
  Latency Distribution
     50%     1.56ms
     75%     1.59ms
     90%     1.63ms
     99%     1.73ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     33347.54     816.80   34071.55
  Latency        1.49ms    55.77us     3.04ms
  Latency Distribution
     50%     1.48ms
     75%     1.50ms
     90%     1.55ms
     99%     1.73ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     30642.09     965.98   32156.66
  Latency        1.62ms    48.70us     2.90ms
  Latency Distribution
     50%     1.62ms
     75%     1.66ms
     90%     1.70ms
     99%     1.88ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     29850.23     787.07   30755.54
  Latency        1.67ms    73.50us     3.49ms
  Latency Distribution
     50%     1.65ms
     75%     1.68ms
     90%     1.72ms
     99%     2.05ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Header Param (/header)
  Reqs/sec     31310.63    1863.01   34409.62
  Latency        1.59ms   212.19us     3.38ms
  Latency Distribution
     50%     1.77ms
     75%     1.86ms
     90%     1.97ms
     99%     2.35ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     30879.97    2768.35   35937.35
  Latency        1.63ms   248.37us     3.27ms
  Latency Distribution
     50%     1.77ms
     75%     1.88ms
     90%     2.01ms
     99%     2.65ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     28425.77    1066.29   29600.90
  Latency        1.75ms    92.62us     3.55ms
  Latency Distribution
     50%     1.72ms
     75%     1.79ms
     90%     1.88ms
     99%     2.34ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     35642.48    2619.25   38280.84
  Latency        1.40ms    88.40us     2.92ms
  Latency Distribution
     50%     1.36ms
     75%     1.44ms
     90%     1.56ms
     99%     2.08ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     31896.51    2092.46   34882.46
  Latency        1.56ms    79.03us     3.69ms
  Latency Distribution
     50%     1.56ms
     75%     1.65ms
     90%     1.69ms
     99%     1.81ms
    1xx - 0, 2xx - 0, 3xx - 10000, 4xx - 0, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     31116.62    1328.45   33107.15
  Latency        1.60ms   246.26us     3.17ms
  Latency Distribution
     50%     1.24ms
     75%     1.52ms
     90%     2.82ms
     99%     2.93ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     28212.63    1387.60   29970.33
  Latency        1.76ms   375.58us     3.81ms
  Latency Distribution
     50%     1.36ms
     75%     1.75ms
     90%     3.09ms
     99%     3.46ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
 5890 / 10000   58.90% 29415/s
  Reqs/sec     30616.95    2242.51   33297.59
  Latency        1.63ms   402.39us     4.01ms
  Latency Distribution
     50%     1.25ms
     75%     1.75ms
     90%     2.79ms
     99%     3.40ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     23270.51    3004.65   29487.49
  Latency        2.15ms   404.17us     4.71ms
  Latency Distribution
     50%     2.20ms
     75%     2.77ms
     90%     2.92ms
     99%     3.49ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     36728.92    1730.56   38477.22
  Latency        1.35ms    87.60us     2.62ms
  Latency Distribution
     50%     1.32ms
     75%     1.37ms
     90%     1.43ms
     99%     1.89ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     35908.71    1828.97   38267.68
  Latency        1.38ms   104.10us     2.81ms
  Latency Distribution
     50%     1.35ms
     75%     1.43ms
     90%     1.48ms
     99%     1.99ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     14627.15     285.30   14814.27
  Latency        3.40ms   111.02us     6.14ms
  Latency Distribution
     50%     3.39ms
     75%     3.43ms
     90%     3.47ms
     99%     3.59ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     14689.95     479.50   15393.50
  Latency        3.39ms   142.55us     5.97ms
  Latency Distribution
     50%     3.36ms
     75%     3.46ms
     90%     3.54ms
     99%     3.99ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     29798.89    4119.94   44357.00
  Latency        1.71ms   241.86us     3.43ms
  Latency Distribution
     50%     1.91ms
     75%     1.99ms
     90%     2.10ms
     99%     2.77ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     27028.63    2330.92   31593.06
  Latency        1.85ms   372.55us     4.69ms
  Latency Distribution
     50%     1.95ms
     75%     2.10ms
     90%     2.43ms
     99%     3.46ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     29113.52    7544.60   57324.48
  Latency        1.80ms   330.94us     4.67ms
  Latency Distribution
     50%     1.93ms
     75%     2.05ms
     90%     2.31ms
     99%     3.11ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     15160.10     398.18   15656.84
  Latency        3.29ms    98.06us     5.13ms
  Latency Distribution
     50%     3.28ms
     75%     3.36ms
     90%     3.41ms
     99%     3.47ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     29984.26    3015.87   32555.19
  Latency        1.67ms   269.45us     4.83ms
  Latency Distribution
     50%     1.83ms
     75%     1.93ms
     90%     2.03ms
     99%     2.65ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     29434.51    3480.74   33862.76
  Latency        1.70ms   284.58us     3.50ms
  Latency Distribution
     50%     1.79ms
     75%     1.91ms
     90%     2.35ms
     99%     2.76ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0
