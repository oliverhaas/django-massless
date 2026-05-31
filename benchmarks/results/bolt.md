# Benchmark report: bolt
Config: C=50 N=10000 target=http://127.0.0.1:8001

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     40043.61    1578.76   42386.60
  Latency        1.24ms   693.06us    20.60ms
  Latency Distribution
     50%     1.21ms
     75%     1.27ms
     90%     1.31ms
     99%     1.60ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     40142.20    3230.75   43665.99
  Latency        1.24ms   212.30us     4.17ms
  Latency Distribution
     50%     1.20ms
     75%     1.26ms
     90%     1.40ms
     99%     2.23ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     26444.12     869.70   27804.41
  Latency        1.88ms    81.93us     3.56ms
  Latency Distribution
     50%     1.87ms
     75%     1.92ms
     90%     1.97ms
     99%     2.30ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     27017.08    2036.10   29361.62
  Latency        1.84ms   123.66us     3.97ms
  Latency Distribution
     50%     1.78ms
     75%     1.92ms
     90%     2.08ms
     99%     2.42ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     35523.64    1892.99   37842.69
  Latency        1.41ms   142.78us     3.67ms
  Latency Distribution
     50%     1.38ms
     75%     1.45ms
     90%     1.48ms
     99%     2.05ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      8132.15     679.15    8929.25
  Latency        6.13ms   486.01us    11.89ms
  Latency Distribution
     50%     6.04ms
     75%     6.35ms
     90%     6.69ms
     99%     8.51ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 500kb JSON (/500k-json)
 3399 / 10000   33.99% 1885/s 00m03s
  Reqs/sec      1915.03      75.97    2182.63
  Latency       26.06ms     1.09ms    33.49ms
  Latency Distribution
     50%    25.88ms
     75%    26.66ms
     90%    27.03ms
     99%    28.88ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1mb JSON (/1m-json)
 175 / 10000    1.75% 873/s 00m11s
 2450 / 10000   24.50% 940/s 00m08s
  Reqs/sec       948.97      34.54    1045.02
  Latency       52.57ms     2.32ms    63.78ms
  Latency Distribution
     50%    52.36ms
     75%    52.75ms
     90%    54.40ms
     99%    58.41ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     32202.87    1280.78   34061.39
  Latency        1.54ms    99.58us     3.36ms
  Latency Distribution
     50%     1.52ms
     75%     1.57ms
     90%     1.64ms
     99%     2.25ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     31821.94     608.58   32192.40
  Latency        1.56ms    59.53us     3.91ms
  Latency Distribution
     50%     1.56ms
     75%     1.59ms
     90%     1.61ms
     99%     1.70ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     31689.54     905.84   32212.68
  Latency        1.57ms    60.86us     3.82ms
  Latency Distribution
     50%     1.56ms
     75%     1.58ms
     90%     1.61ms
     99%     1.75ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     27987.36    2675.19   30489.01
  Latency        1.78ms   282.52us     8.09ms
  Latency Distribution
     50%     1.69ms
     75%     1.87ms
     90%     1.99ms
     99%     3.21ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Header Param (/header)
  Reqs/sec     30312.02    1811.90   33483.96
  Latency        1.65ms   229.65us     4.10ms
  Latency Distribution
     50%     1.82ms
     75%     1.93ms
     90%     2.05ms
     99%     2.47ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     32808.68    7045.96   59494.53
  Latency        1.60ms   176.63us     4.25ms
  Latency Distribution
     50%     1.80ms
     75%     1.87ms
     90%     1.95ms
     99%     2.21ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     31252.08    1015.50   32067.18
  Latency        1.59ms    66.43us     3.38ms
  Latency Distribution
     50%     1.57ms
     75%     1.61ms
     90%     1.66ms
     99%     1.86ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     37389.32    1868.93   39493.29
  Latency        1.33ms    64.91us     2.55ms
  Latency Distribution
     50%     1.29ms
     75%     1.38ms
     90%     1.45ms
     99%     1.74ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     31760.15    1547.16   33905.21
  Latency        1.57ms    86.74us     3.23ms
  Latency Distribution
     50%     1.56ms
     75%     1.61ms
     90%     1.71ms
     99%     1.80ms
    1xx - 0, 2xx - 0, 3xx - 10000, 4xx - 0, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     30742.69    1130.11   33891.93
  Latency        1.63ms   273.60us     3.54ms
  Latency Distribution
     50%     1.24ms
     75%     1.56ms
     90%     2.81ms
     99%     3.06ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     28699.90    1066.31   29515.66
  Latency        1.74ms   274.19us     4.52ms
  Latency Distribution
     50%     1.34ms
     75%     1.52ms
     90%     2.99ms
     99%     3.19ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     31641.33    1062.14   33183.53
  Latency        1.57ms   247.38us     3.45ms
  Latency Distribution
     50%     1.20ms
     75%     1.46ms
     90%     2.74ms
     99%     2.89ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     25637.03    2301.28   27625.69
  Latency        1.95ms   322.91us     3.82ms
  Latency Distribution
     50%     2.16ms
     75%     2.26ms
     90%     2.39ms
     99%     3.46ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     34197.29    1246.99   36560.75
  Latency        1.45ms    86.90us     2.85ms
  Latency Distribution
     50%     1.44ms
     75%     1.49ms
     90%     1.55ms
     99%     1.76ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     35644.54    1445.90   38474.96
  Latency        1.39ms    56.56us     3.41ms
  Latency Distribution
     50%     1.39ms
     75%     1.45ms
     90%     1.48ms
     99%     1.57ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     14612.76     568.30   15610.72
  Latency        3.41ms   137.94us     5.58ms
  Latency Distribution
     50%     3.37ms
     75%     3.43ms
     90%     3.63ms
     99%     4.00ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     14582.91     447.14   15151.15
  Latency        3.42ms   135.71us     6.08ms
  Latency Distribution
     50%     3.42ms
     75%     3.47ms
     90%     3.53ms
     99%     3.79ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Post Branch (/feed/0)
 5790 / 10000   57.90% 28847/s
  Reqs/sec     28732.89    1513.38   31321.55
  Latency        1.73ms   280.09us     3.31ms
  Latency Distribution
     50%     1.90ms
     75%     2.02ms
     90%     2.14ms
     99%     2.86ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     30272.83    5381.55   50082.96
  Latency        1.71ms   263.10us     4.17ms
  Latency Distribution
     50%     1.92ms
     75%     1.98ms
     90%     2.06ms
     99%     2.72ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     26983.32    1961.19   30748.23
  Latency        1.85ms   321.05us     4.62ms
  Latency Distribution
     50%     1.97ms
     75%     2.13ms
     90%     2.43ms
     99%     3.00ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     15660.39     464.55   15977.32
  Latency        3.18ms   116.74us     4.76ms
  Latency Distribution
     50%     3.16ms
     75%     3.20ms
     90%     3.27ms
     99%     3.67ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     27505.74    4379.70   35944.00
  Latency        1.83ms   285.37us     4.65ms
  Latency Distribution
     50%     1.87ms
     75%     2.33ms
     90%     2.49ms
     99%     2.77ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     28691.47    3460.61   34338.56
  Latency        1.75ms   265.79us     4.43ms
  Latency Distribution
     50%     1.85ms
     75%     1.99ms
     90%     2.40ms
     99%     2.68ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0
