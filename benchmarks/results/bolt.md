# Benchmark report: bolt
Config: C=50 N=10000 target=http://127.0.0.1:8001

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     38301.83    2378.45   40578.89
  Latency        1.30ms   366.67us    11.52ms
  Latency Distribution
     50%     1.26ms
     75%     1.31ms
     90%     1.40ms
     99%     2.02ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     38741.38     978.90   40347.82
  Latency        1.28ms   148.30us     3.37ms
  Latency Distribution
     50%     1.27ms
     75%     1.31ms
     90%     1.36ms
     99%     1.79ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     25681.50     583.72   26308.74
  Latency        1.94ms    55.65us     4.32ms
  Latency Distribution
     50%     1.93ms
     75%     1.96ms
     90%     1.99ms
     99%     2.10ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     26299.01     771.25   26927.30
  Latency        1.89ms    76.20us     4.06ms
  Latency Distribution
     50%     1.88ms
     75%     1.91ms
     90%     1.95ms
     99%     2.15ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     34414.33    1155.51   35840.69
  Latency        1.44ms   150.01us     4.28ms
  Latency Distribution
     50%     1.44ms
     75%     1.47ms
     90%     1.51ms
     99%     1.68ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec      8522.58     397.24    8818.80
  Latency        5.85ms   280.14us    13.87ms
  Latency Distribution
     50%     5.80ms
     75%     5.90ms
     90%     6.04ms
     99%     6.92ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 500kb JSON (/500k-json)
 3850 / 10000   38.50% 1922/s 00m03s
  Reqs/sec      1905.07      77.78    2110.01
  Latency       26.18ms     1.17ms    33.62ms
  Latency Distribution
     50%    26.00ms
     75%    26.56ms
     90%    27.39ms
     99%    29.39ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1mb JSON (/1m-json)
 3690 / 10000   36.90% 920/s 00m06s
 5775 / 10000   57.75% 929/s 00m04s
  Reqs/sec       934.47      44.85    1147.51
  Latency       53.39ms     2.62ms    68.06ms
  Latency Distribution
     50%    52.87ms
     75%    53.62ms
     90%    55.72ms
     99%    63.61ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     33381.60     442.82   33726.63
  Latency        1.49ms    59.12us     3.37ms
  Latency Distribution
     50%     1.49ms
     75%     1.50ms
     90%     1.53ms
     99%     1.57ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     31015.88     248.91   31340.74
  Latency        1.60ms    47.13us     2.75ms
  Latency Distribution
     50%     1.60ms
     75%     1.63ms
     90%     1.65ms
     99%     1.71ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     30521.21    1747.22   31439.97
  Latency        1.63ms   221.96us     5.52ms
  Latency Distribution
     50%     1.60ms
     75%     1.63ms
     90%     1.66ms
     99%     1.95ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     28403.13     774.77   30261.06
  Latency        1.75ms    65.37us     3.07ms
  Latency Distribution
     50%     1.77ms
     75%     1.79ms
     90%     1.82ms
     99%     1.89ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Header Param (/header)
  Reqs/sec     29165.36    3557.47   38430.03
  Latency        1.73ms   295.16us     3.37ms
  Latency Distribution
     50%     1.82ms
     75%     2.01ms
     90%     2.17ms
     99%     2.94ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     28310.91    4156.43   33597.62
  Latency        1.77ms   313.08us     3.92ms
  Latency Distribution
     50%     1.82ms
     75%     2.01ms
     90%     2.56ms
     99%     3.04ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     28136.27    1804.53   30899.49
  Latency        1.77ms   120.85us     3.96ms
  Latency Distribution
     50%     1.75ms
     75%     1.79ms
     90%     1.91ms
     99%     2.43ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
 6499 / 10000   64.99% 32457/s
  Reqs/sec     33148.34    1296.22   35231.26
  Latency        1.50ms    63.66us     2.86ms
  Latency Distribution
     50%     1.52ms
     75%     1.55ms
     90%     1.60ms
     99%     1.76ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     30260.38    1764.41   31532.74
  Latency        1.65ms   108.06us     3.29ms
  Latency Distribution
     50%     1.60ms
     75%     1.65ms
     90%     1.73ms
     99%     2.33ms
    1xx - 0, 2xx - 0, 3xx - 10000, 4xx - 0, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     30654.11    1360.89   33181.99
  Latency        1.62ms   259.75us     3.71ms
  Latency Distribution
     50%     1.25ms
     75%     1.68ms
     90%     2.85ms
     99%     2.94ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     27873.86     718.82   29218.83
  Latency        1.79ms   274.78us     3.63ms
  Latency Distribution
     50%     1.37ms
     75%     1.64ms
     90%     3.13ms
     99%     3.24ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     31926.20    1424.17   32964.67
  Latency        1.56ms   274.82us     4.60ms
  Latency Distribution
     50%     1.19ms
     75%     1.82ms
     90%     2.67ms
     99%     2.91ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     24906.48    3376.76   28878.98
  Latency        2.02ms   386.13us     4.58ms
  Latency Distribution
     50%     2.16ms
     75%     2.29ms
     90%     2.63ms
     99%     3.38ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     34586.84    1309.73   37407.86
  Latency        1.44ms    89.09us     3.57ms
  Latency Distribution
     50%     1.45ms
     75%     1.48ms
     90%     1.52ms
     99%     1.69ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     34603.24    1546.73   36860.86
  Latency        1.44ms    98.27us     3.51ms
  Latency Distribution
     50%     1.45ms
     75%     1.47ms
     90%     1.51ms
     99%     1.65ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     15363.15     311.07   15724.78
  Latency        3.24ms   116.81us     5.79ms
  Latency Distribution
     50%     3.23ms
     75%     3.26ms
     90%     3.31ms
     99%     3.73ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     15022.15     262.54   15188.81
  Latency        3.32ms   112.05us     5.42ms
  Latency Distribution
     50%     3.31ms
     75%     3.33ms
     90%     3.37ms
     99%     3.54ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     28131.11    2276.52   32402.68
  Latency        1.78ms   242.45us     3.69ms
  Latency Distribution
     50%     1.96ms
     75%     2.07ms
     90%     2.18ms
     99%     2.90ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     29105.91    2056.40   34885.49
  Latency        1.73ms   233.11us     3.24ms
  Latency Distribution
     50%     1.91ms
     75%     2.04ms
     90%     2.14ms
     99%     2.31ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     29209.64    1501.37   31530.13
  Latency        1.71ms   207.47us     3.69ms
  Latency Distribution
     50%     1.93ms
     75%     2.01ms
     90%     2.10ms
     99%     2.35ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     14896.03     252.89   15640.49
  Latency        3.34ms   108.79us     6.73ms
  Latency Distribution
     50%     3.34ms
     75%     3.37ms
     90%     3.41ms
     99%     3.54ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     30171.69    2036.53   32879.30
  Latency        1.66ms   249.05us     3.59ms
  Latency Distribution
     50%     1.82ms
     75%     1.92ms
     90%     2.06ms
     99%     2.62ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     29505.15    2045.44   32555.03
  Latency        1.69ms   268.56us     4.49ms
  Latency Distribution
     50%     1.84ms
     75%     1.96ms
     90%     2.08ms
     99%     2.66ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0
