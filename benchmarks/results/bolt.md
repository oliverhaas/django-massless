# Benchmark report: bolt
Config: C=50 N=10000 target=http://127.0.0.1:8001

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     75923.71    4810.06   79868.63
  Latency      647.61us   100.97us     2.39ms
  Latency Distribution
     50%   604.00us
     75%   737.00us
     90%   796.00us
     99%     1.20ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     80319.39    3094.57   83719.44
  Latency      615.12us    87.24us     2.36ms
  Latency Distribution
     50%   621.00us
     75%   648.00us
     90%   703.00us
     99%     0.93ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     52697.46    2302.43   55632.79
  Latency        0.94ms    85.66us     2.62ms
  Latency Distribution
     50%     1.04ms
     75%     1.08ms
     90%     1.13ms
     99%     1.45ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     52172.59    2942.29   55750.93
  Latency        0.95ms   103.69us     3.24ms
  Latency Distribution
     50%     1.02ms
     75%     1.13ms
     90%     1.18ms
     99%     1.38ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     68519.70    2949.77   70548.71
  Latency      724.37us    67.38us     2.08ms
  Latency Distribution
     50%   747.00us
     75%   768.00us
     90%   807.00us
     99%     1.03ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec     17486.35     605.51   18005.79
  Latency        2.84ms   186.24us     6.13ms
  Latency Distribution
     50%     2.68ms
     75%     3.18ms
     90%     3.27ms
     99%     3.60ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 500kb JSON (/500k-json)
 2290 / 10000   22.90% 3813/s 00m02s
 6990 / 10000   69.90% 3880/s
 8550 / 10000   85.50% 3882/s
  Reqs/sec      3889.10     132.38    4163.78
  Latency       12.82ms   674.82us    24.83ms
  Latency Distribution
     50%    12.88ms
     75%    13.23ms
     90%    13.73ms
     99%    15.11ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec      2017.16    2012.56   34645.23
  Latency       26.34ms     0.92ms    34.52ms
  Latency Distribution
     50%    26.28ms
     75%    26.44ms
     90%    26.66ms
     99%    28.48ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     65695.35    2983.55   68563.21
  Latency      755.54us    99.53us     2.61ms
  Latency Distribution
     50%   812.00us
     75%     0.85ms
     90%     0.90ms
     99%     1.21ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     65484.77    2962.61   67981.55
  Latency      758.80us    68.48us     2.22ms
  Latency Distribution
     50%   745.00us
     75%   772.00us
     90%   822.00us
     99%     1.02ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     61242.72    1812.37   63608.84
  Latency      808.46us    50.15us     2.24ms
  Latency Distribution
     50%   822.00us
     75%     0.88ms
     90%     0.90ms
     99%     0.97ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     58074.96    2387.33   61247.85
  Latency        0.85ms    70.84us     2.22ms
  Latency Distribution
     50%     1.06ms
     75%     1.12ms
     90%     1.14ms
     99%     1.20ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Header Param (/header)
  Reqs/sec     53896.57    2902.68   58006.55
  Latency        0.93ms   168.40us     2.40ms
  Latency Distribution
     50%   817.00us
     75%     1.08ms
     90%     1.24ms
     99%     1.96ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     57219.58    5146.14   62530.65
  Latency        0.87ms   165.86us     2.56ms
  Latency Distribution
     50%     0.90ms
     75%     0.96ms
     90%     1.24ms
     99%     1.71ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     58104.94    2210.67   60158.97
  Latency        0.86ms    44.06us     2.23ms
  Latency Distribution
     50%     0.89ms
     75%     0.94ms
     90%     0.97ms
     99%     1.03ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     69465.63    4406.43   72993.77
  Latency      703.06us    69.32us     2.45ms
  Latency Distribution
     50%   750.00us
     75%   785.00us
     90%   839.00us
     99%     1.04ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     64952.06    2987.13   67572.35
  Latency      764.66us    67.83us     2.72ms
  Latency Distribution
     50%   657.00us
     75%     0.93ms
     90%     0.97ms
     99%     1.03ms
    1xx - 0, 2xx - 0, 3xx - 10000, 4xx - 0, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     60722.13    4659.10   64170.29
  Latency      800.63us   123.28us     3.93ms
  Latency Distribution
     50%   732.00us
     75%     0.93ms
     90%     0.97ms
     99%     1.14ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     56606.35    3249.36   58967.15
  Latency        0.88ms    93.49us     3.03ms
  Latency Distribution
     50%   807.00us
     75%     0.95ms
     90%     1.05ms
     99%     1.21ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     58687.61    4338.28   63010.84
  Latency      846.14us    68.09us     2.54ms
  Latency Distribution
     50%     0.87ms
     75%     0.92ms
     90%     0.97ms
     99%     1.16ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     44525.13    4221.11   50551.10
  Latency        1.13ms   242.66us     3.26ms
  Latency Distribution
     50%     1.02ms
     75%     1.25ms
     90%     1.56ms
     99%     2.40ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     65595.33    4697.08   71864.42
  Latency      758.66us    75.50us     2.31ms
  Latency Distribution
     50%   764.00us
     75%   798.00us
     90%     0.85ms
     99%     0.98ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     66424.72    2320.81   67893.15
  Latency      746.34us    75.90us     2.62ms
  Latency Distribution
     50%   734.00us
     75%   820.00us
     90%     0.85ms
     99%     1.02ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     29492.46    1442.46   30666.06
  Latency        1.69ms   143.59us     3.81ms
  Latency Distribution
     50%     1.83ms
     75%     1.94ms
     90%     2.05ms
     99%     2.44ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     28537.40    3450.96   29837.68
  Latency        1.69ms   150.06us     3.99ms
  Latency Distribution
     50%     1.21ms
     75%     2.30ms
     90%     2.36ms
     99%     2.42ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     46897.40    4350.50   53933.90
  Latency        1.06ms   188.02us     2.88ms
  Latency Distribution
     50%     1.01ms
     75%     1.17ms
     90%     1.35ms
     99%     2.08ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Comment Branch (/feed/1)
 9975 / 10000   99.75% 49820/s
  Reqs/sec     57789.23   26920.68  138451.42
  Latency        1.00ms   175.86us     2.91ms
  Latency Distribution
     50%     0.94ms
     75%     1.03ms
     90%     1.34ms
     99%     1.90ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     48832.05    5354.61   56443.80
  Latency        1.03ms   166.69us     3.02ms
  Latency Distribution
     50%     0.99ms
     75%     1.09ms
     90%     1.27ms
     99%     1.94ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     30569.55    1079.66   31395.92
  Latency        1.63ms    80.75us     4.29ms
  Latency Distribution
     50%     1.62ms
     75%     1.64ms
     90%     1.68ms
     99%     1.88ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     55516.08    3237.65   58311.47
  Latency        0.89ms   200.28us     3.09ms
  Latency Distribution
     50%     0.93ms
     75%     1.08ms
     90%     1.26ms
     99%     1.91ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     50656.42    3855.79   56534.67
  Latency        0.98ms   164.78us     3.07ms
  Latency Distribution
     50%     0.95ms
     75%     1.05ms
     90%     1.19ms
     99%     1.86ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0
