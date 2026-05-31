# Benchmark report: massless
Config: C=50 N=10000 target=http://127.0.0.1:8000

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     76560.16   21612.70   97053.84
  Latency      658.96us     0.98ms    25.86ms
  Latency Distribution
     50%   567.00us
     75%   606.00us
     90%   627.00us
     99%     1.22ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     93950.70    6102.45  103712.20
  Latency      534.68us   348.28us    11.99ms
  Latency Distribution
     50%   513.00us
     75%   559.00us
     90%   577.00us
     99%     1.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     40114.63    3163.11   44114.15
  Latency        1.25ms     0.99ms    32.03ms
  Latency Distribution
     50%     1.18ms
     75%     1.24ms
     90%     1.28ms
     99%     2.44ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec     87977.88   10402.79  100676.55
  Latency      564.86us   370.46us    11.92ms
  Latency Distribution
     50%   543.00us
     75%   570.00us
     90%   587.00us
     99%     1.13ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec     91310.82    2369.70   95121.05
  Latency      541.75us   268.97us     9.43ms
  Latency Distribution
     50%   505.00us
     75%   566.00us
     90%   593.00us
     99%     1.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec     91690.99    5546.84   97531.63
  Latency      543.80us   327.91us    11.78ms
  Latency Distribution
     50%   517.00us
     75%   559.00us
     90%   587.00us
     99%     1.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec    109422.72   28132.96  166377.98
  Latency      504.52us   245.50us     8.16ms
  Latency Distribution
     50%   468.00us
     75%   521.00us
     90%   561.00us
     99%     1.00ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec     90857.53    7834.19  101623.19
  Latency      540.00us   338.26us    11.04ms
  Latency Distribution
     50%   517.00us
     75%   564.00us
     90%   596.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     76395.96    5141.08   81296.18
  Latency      652.27us   470.10us    15.70ms
  Latency Distribution
     50%   615.00us
     75%   652.00us
     90%   680.00us
     99%     1.26ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     81412.79   29713.72  154029.80
  Latency      698.66us   281.29us    10.69ms
  Latency Distribution
     50%   695.00us
     75%   717.00us
     90%   734.00us
     99%     1.40ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     88748.80    8045.03  101428.95
  Latency      559.63us   373.06us    11.45ms
  Latency Distribution
     50%   514.00us
     75%   590.00us
     90%   616.00us
     99%     1.10ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     84779.73    6516.37   91046.25
  Latency      585.94us   430.20us    13.32ms
  Latency Distribution
     50%   567.00us
     75%   586.00us
     90%   599.00us
     99%     1.14ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
  Reqs/sec     87531.14    9807.31   95952.74
  Latency      569.54us   396.29us    13.86ms
  Latency Distribution
     50%   523.00us
     75%   587.00us
     90%   638.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     84513.13    5796.27   89175.58
  Latency      585.60us   351.67us    11.72ms
  Latency Distribution
     50%   558.00us
     75%   577.00us
     90%   612.00us
     99%     1.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     89872.78   12281.12  107718.68
  Latency      558.39us   360.52us    12.14ms
  Latency Distribution
     50%   505.00us
     75%   592.00us
     90%   648.00us
     99%     1.23ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     91475.19    9746.96  101123.32
  Latency      543.76us   360.96us    12.90ms
  Latency Distribution
     50%   513.00us
     75%   552.00us
     90%   577.00us
     99%     1.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     89249.47    7187.51   96404.43
  Latency      559.13us   306.88us    11.43ms
  Latency Distribution
     50%   534.00us
     75%   558.00us
     90%   580.00us
     99%     1.10ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     80689.18    6362.14   87774.06
  Latency      620.63us   328.78us    11.84ms
  Latency Distribution
     50%   585.00us
     75%   638.00us
     90%   683.00us
     99%     1.19ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     85419.81   10414.56  105956.07
  Latency      603.06us   368.65us    12.87ms
  Latency Distribution
     50%   565.00us
     75%   616.00us
     90%   661.00us
     99%     1.15ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     81735.24    7324.71   94282.50
  Latency      618.52us   430.72us    13.89ms
  Latency Distribution
     50%   592.00us
     75%   610.00us
     90%   648.00us
     99%     1.18ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     86425.26    5918.22   91863.72
  Latency      575.04us   390.82us    13.12ms
  Latency Distribution
     50%   546.00us
     75%   567.00us
     90%   596.00us
     99%     1.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     89017.83   10391.57  103451.60
  Latency      556.72us   382.89us    12.95ms
  Latency Distribution
     50%   518.00us
     75%   561.00us
     90%   604.00us
     99%     1.16ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     82117.27   10510.64   91946.72
  Latency      615.67us   450.28us    11.49ms
  Latency Distribution
     50%   571.00us
     75%   587.00us
     90%   668.00us
     99%     1.16ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     85838.09    2868.81   88330.67
  Latency      576.57us   287.50us    11.12ms
  Latency Distribution
     50%   555.00us
     75%   588.00us
     90%   635.00us
     99%     1.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     86490.14    7553.34   95169.19
  Latency      573.43us   426.36us    14.24ms
  Latency Distribution
     50%   536.00us
     75%   567.00us
     90%   630.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     86017.95    3993.62   90197.93
  Latency      577.27us   273.83us     9.77ms
  Latency Distribution
     50%   548.00us
     75%   573.00us
     90%   613.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     87900.17    7785.78   94966.13
  Latency      564.94us   448.99us    14.38ms
  Latency Distribution
     50%   526.00us
     75%   556.00us
     90%   624.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     90944.43    8001.67   99175.64
  Latency      549.56us   359.54us    12.01ms
  Latency Distribution
     50%   523.00us
     75%   570.00us
     90%   594.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     87234.96    9873.96   97573.75
  Latency      573.36us   365.76us    12.19ms
  Latency Distribution
     50%   544.00us
     75%   584.00us
     90%   642.00us
     99%     1.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     87705.33    6447.94   93541.20
  Latency      566.04us   266.95us     9.48ms
  Latency Distribution
     50%   540.00us
     75%   564.00us
     90%   626.00us
     99%     1.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     83685.11    4254.66   87539.01
  Latency      591.35us   225.05us     8.27ms
  Latency Distribution
     50%   573.00us
     75%   586.00us
     90%   618.00us
     99%     1.15ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
