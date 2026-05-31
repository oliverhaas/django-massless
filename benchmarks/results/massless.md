# Benchmark report: massless
Config: C=50 N=10000 target=http://127.0.0.1:8000

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     83307.06    5729.53   87869.34
  Latency      595.24us   141.48us     3.99ms
  Latency Distribution
     50%   569.00us
     75%   642.00us
     90%   745.00us
     99%     0.92ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     94354.57    5334.88   99770.61
  Latency      525.16us   100.90us     3.10ms
  Latency Distribution
     50%   505.00us
     75%   574.00us
     90%   667.00us
     99%     0.85ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     49905.79    1904.83   52256.17
  Latency        1.00ms   160.62us     4.25ms
  Latency Distribution
     50%     0.93ms
     75%     1.06ms
     90%     1.29ms
     99%     1.67ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     93971.90    7137.72  100761.41
  Latency      530.27us   107.22us     3.63ms
  Latency Distribution
     50%   506.00us
     75%   577.00us
     90%   670.00us
     99%   839.00us
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     91938.95   16000.62  108726.02
  Latency      542.35us   453.71us     8.50ms
  Latency Distribution
     50%   491.00us
     75%   562.00us
     90%   647.00us
     99%     0.93ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec     93470.16    5145.53   98102.90
  Latency      531.22us    91.38us     2.52ms
  Latency Distribution
     50%   513.00us
     75%   587.00us
     90%   673.00us
     99%     0.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec     94578.31    5299.52  101752.63
  Latency      525.26us   114.62us     2.86ms
  Latency Distribution
     50%   496.00us
     75%   584.00us
     90%   676.00us
     99%     0.91ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec     91004.37    4030.88   94071.86
  Latency      543.07us   103.20us     2.98ms
  Latency Distribution
     50%   527.00us
     75%   602.00us
     90%   692.00us
     99%     0.92ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     75963.11    4198.37   79843.51
  Latency      655.38us   108.10us     3.68ms
  Latency Distribution
     50%   624.00us
     75%   721.00us
     90%   824.00us
     99%     1.07ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     71082.66    3613.44   75387.22
  Latency      703.97us   150.15us     4.73ms
  Latency Distribution
     50%   678.00us
     75%   792.00us
     90%     0.90ms
     99%     1.28ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     91209.40    5112.56   95347.70
  Latency      545.42us    93.23us     3.49ms
  Latency Distribution
     50%   523.00us
     75%   593.00us
     90%   679.00us
     99%     0.88ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     91294.24    5727.03   96089.31
  Latency      545.67us    90.38us     2.71ms
  Latency Distribution
     50%   528.00us
     75%   595.00us
     90%   687.00us
     99%     0.87ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
  Reqs/sec     85913.12    7904.73   91918.92
  Latency      578.44us   161.00us     3.48ms
  Latency Distribution
     50%   544.00us
     75%   635.00us
     90%   730.00us
     99%     0.95ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     94297.81    4764.08   98081.93
  Latency      527.98us   112.57us     3.98ms
  Latency Distribution
     50%   502.00us
     75%   576.00us
     90%   681.00us
     99%     0.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     93095.67    3789.73   97344.08
  Latency      533.75us    94.30us     2.83ms
  Latency Distribution
     50%   511.00us
     75%   589.00us
     90%   676.00us
     99%     0.91ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     92362.21    6070.64   95761.81
  Latency      537.69us   104.59us     3.23ms
  Latency Distribution
     50%   506.00us
     75%   599.00us
     90%   695.00us
     99%     0.95ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     90580.95    6452.44   96419.13
  Latency      548.65us   113.09us     3.69ms
  Latency Distribution
     50%   521.00us
     75%   607.00us
     90%   689.00us
     99%     0.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     88597.93    6192.94   96516.18
  Latency      557.85us   110.85us     4.02ms
  Latency Distribution
     50%   529.00us
     75%   625.00us
     90%   733.00us
     99%     1.02ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     88287.75    5163.05   94871.34
  Latency      562.44us   142.41us     5.01ms
  Latency Distribution
     50%   550.00us
     75%   619.00us
     90%   758.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     87195.94    3617.41   90134.30
  Latency      568.57us   124.17us     3.25ms
  Latency Distribution
     50%   555.00us
     75%   637.00us
     90%   759.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     90395.98    4158.16   94897.56
  Latency      546.68us   105.09us     2.90ms
  Latency Distribution
     50%   535.00us
     75%   604.00us
     90%   722.00us
     99%     0.97ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     90221.27   12918.08  101063.49
  Latency      550.39us   450.19us    11.84ms
  Latency Distribution
     50%   500.00us
     75%   584.00us
     90%   660.00us
     99%     0.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     90461.03    3757.33   94494.02
  Latency      544.37us    84.62us     2.47ms
  Latency Distribution
     50%   521.00us
     75%   599.00us
     90%   684.00us
     99%     0.91ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     92359.95    4976.01   97294.10
  Latency      539.50us   113.92us     3.80ms
  Latency Distribution
     50%   511.00us
     75%   597.00us
     90%   689.00us
     99%     0.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     90595.45    5771.74  100053.46
  Latency      543.13us   134.16us     3.86ms
  Latency Distribution
     50%   545.00us
     75%   647.00us
     90%   779.00us
     99%     1.10ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     94527.53    6214.38  102426.79
  Latency      530.60us   110.02us     3.49ms
  Latency Distribution
     50%   501.00us
     75%   585.00us
     90%   663.00us
     99%     0.90ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     92765.83   14184.90  107678.83
  Latency      543.21us   540.64us    12.34ms
  Latency Distribution
     50%   487.00us
     75%   573.00us
     90%   646.00us
     99%     0.86ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     90084.44    3447.05   93858.75
  Latency      548.74us   116.98us     3.57ms
  Latency Distribution
     50%   524.00us
     75%   609.00us
     90%   704.00us
     99%     0.95ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     88987.00    5986.17   93485.85
  Latency      557.20us   125.71us     3.77ms
  Latency Distribution
     50%   520.00us
     75%   620.00us
     90%   706.00us
     99%     0.95ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     88285.23    5709.87   92419.08
  Latency      563.44us   157.33us     4.81ms
  Latency Distribution
     50%   572.00us
     75%   673.00us
     90%   780.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     87732.17    7799.29   93442.41
  Latency      566.38us   212.16us     5.06ms
  Latency Distribution
     50%   531.00us
     75%   612.00us
     90%   699.00us
     99%     0.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
