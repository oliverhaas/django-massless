# Benchmark report: massless
Config: C=50 N=10000 target=http://127.0.0.1:8000

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     63553.50   28718.88   81352.04
  Latency      786.29us     1.78ms    42.28ms
  Latency Distribution
     50%   589.00us
     75%   647.00us
     90%   802.00us
     99%     1.35ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     88132.19    6759.58   93883.72
  Latency      566.09us   436.14us    14.05ms
  Latency Distribution
     50%   535.00us
     75%   573.00us
     90%   608.00us
     99%     1.13ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     38300.21    4004.93   42858.99
  Latency        1.30ms   728.13us    27.42ms
  Latency Distribution
     50%     1.22ms
     75%     1.29ms
     90%     1.44ms
     99%     2.48ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec    101557.64   17157.51  114431.51
  Latency      501.08us   344.68us     8.60ms
  Latency Distribution
     50%   454.00us
     75%   463.00us
     90%   478.00us
     99%     0.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     94825.97    8736.71  111431.48
  Latency      533.85us   331.40us    11.69ms
  Latency Distribution
     50%   532.00us
     75%   552.00us
     90%   567.00us
     99%     0.99ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec     99341.30    8824.98  109024.95
  Latency      507.97us   301.22us    11.43ms
  Latency Distribution
     50%   471.00us
     75%   509.00us
     90%   562.00us
     99%     0.93ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec    106841.61    6809.87  110908.14
  Latency      464.02us   215.08us     7.63ms
  Latency Distribution
     50%   444.00us
     75%   452.00us
     90%   460.00us
     99%     0.89ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec     95914.66    9662.12  105888.78
  Latency      517.05us   334.00us    11.52ms
  Latency Distribution
     50%   484.00us
     75%   535.00us
     90%   561.00us
     99%     1.01ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     73361.61    5698.63   82795.11
  Latency      679.46us   335.19us    12.34ms
  Latency Distribution
     50%   651.00us
     75%   673.00us
     90%   722.00us
     99%     1.35ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     80700.12   28649.77  151348.68
  Latency      700.48us   463.53us    14.77ms
  Latency Distribution
     50%   689.00us
     75%   722.00us
     90%   744.00us
     99%     1.35ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     88320.67   12834.63  103872.06
  Latency      567.00us   402.82us    13.52ms
  Latency Distribution
     50%   518.00us
     75%   595.00us
     90%   660.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     85481.11    4831.91   90049.51
  Latency      580.85us   323.10us    11.34ms
  Latency Distribution
     50%   553.00us
     75%   575.00us
     90%   600.00us
     99%     1.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
  Reqs/sec     86013.65    5006.91   94361.59
  Latency      575.20us   258.94us    10.10ms
  Latency Distribution
     50%   564.00us
     75%   588.00us
     90%   627.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     84840.93    8957.44  101424.92
  Latency      600.64us   144.63us     5.98ms
  Latency Distribution
     50%   574.00us
     75%   607.00us
     90%   675.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     86780.65   12549.28  109685.20
  Latency      598.33us   346.80us    11.83ms
  Latency Distribution
     50%   578.00us
     75%   605.00us
     90%   635.00us
     99%     1.19ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     79656.05   12149.97   91936.54
  Latency      627.82us   348.77us     9.70ms
  Latency Distribution
     50%   555.00us
     75%   580.00us
     90%   677.00us
     99%     2.16ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     83593.53   11932.51   92128.55
  Latency      594.25us   436.03us    15.23ms
  Latency Distribution
     50%   541.00us
     75%   595.00us
     90%   688.00us
     99%     1.20ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     80288.45    4438.72   84565.52
  Latency      619.91us   181.06us     7.98ms
  Latency Distribution
     50%   598.00us
     75%   619.00us
     90%   653.00us
     99%     1.20ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     85433.08    4778.56   88899.73
  Latency      580.16us   384.59us    13.54ms
  Latency Distribution
     50%   551.00us
     75%   577.00us
     90%   611.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     96811.96   38615.50  183457.53
  Latency      599.39us   283.82us    10.30ms
  Latency Distribution
     50%   578.00us
     75%   597.00us
     90%   614.00us
     99%     1.15ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     80645.70    6952.45   90528.54
  Latency      622.88us   335.71us    11.29ms
  Latency Distribution
     50%   587.00us
     75%   612.00us
     90%   771.00us
     99%     1.17ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     88752.82    6763.55   96975.51
  Latency      561.45us   380.67us    13.15ms
  Latency Distribution
     50%   526.00us
     75%   563.00us
     90%   613.00us
     99%     1.23ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     76043.75    8705.25   88353.53
  Latency      651.06us   403.44us    11.10ms
  Latency Distribution
     50%   574.00us
     75%   646.00us
     90%   759.00us
     99%     1.71ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     81192.83   11855.53   93165.66
  Latency      617.27us   364.69us     9.05ms
  Latency Distribution
     50%   547.00us
     75%   594.00us
     90%   740.00us
     99%     1.81ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     78229.83    5685.39   83858.20
  Latency      628.14us   423.71us    13.82ms
  Latency Distribution
     50%   589.00us
     75%   626.00us
     90%   715.00us
     99%     1.22ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     79034.04    8390.09   93317.40
  Latency      616.96us   350.13us    11.83ms
  Latency Distribution
     50%   575.00us
     75%   615.00us
     90%   740.00us
     99%     1.23ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     71672.60    5692.60   77168.76
  Latency      691.70us   390.95us    13.43ms
  Latency Distribution
     50%   637.00us
     75%   705.00us
     90%   828.00us
     99%     1.33ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     83522.40    7603.99   92608.35
  Latency      593.45us   420.89us    13.44ms
  Latency Distribution
     50%   557.00us
     75%   593.00us
     90%   643.00us
     99%     1.13ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     88106.63   16797.45  120691.16
  Latency      600.48us   506.82us    16.81ms
  Latency Distribution
     50%   570.00us
     75%   584.00us
     90%   601.00us
     99%     1.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     83723.93   10993.96   98041.43
  Latency      594.95us   387.18us    13.30ms
  Latency Distribution
     50%   557.00us
     75%   601.00us
     90%   686.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     87440.74    4134.66   90688.69
  Latency      567.63us   365.74us    12.02ms
  Latency Distribution
     50%   548.00us
     75%   564.00us
     90%   593.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
