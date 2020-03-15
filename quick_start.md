
<!-- prefix https://github.com/ClericPy/watchdogs/raw/master/ -->

# Given a mission
    get the most popular repository in the github python trending page.
   1. Here crawl and parse the HTML from https://github.com/trending/python?since=daily
   2. ~~Although you can get it from the api.github.com~~

# Create a CrawlerRule

1. Get the request args
   1. Use the URL: https://github.com/trending/python?since=daily
   2. Or copy the curl-string from chrome
      1. Chrome dev tools -> Network -> url (RClick) -> Copy -> Copy as cURL
      2. some scenes need the cookie authentication or headers anti-crawler.
      3. ![Copy cURL](https://github.com/ClericPy/watchdogs/raw/master/images/d1.png)
2. Create crawler rule
   1. Open watchdog page. Default http://127.0.0.1:9901/
   2. Click \<New\> tab.
   3. First step is to set the CrawlerRule's meta info.
      1. Now start to ensure the request is correct.
      2. Click \<cURL Parse\> link.
      3. Input the cURL string or URL got before.
      4. ![](https://github.com/ClericPy/watchdogs/raw/master/images/d2.png)
      5. Then it generates the default regex & request args, maybe need some change for match more url pattern.
      6. Click \<Download\> button, wait for it finish downloading => Response Body [200]
         1. If after downloading, \<Rule Name\> is still null, need to input manually.
      7. Check the source code downloaded, ensure it is what you want.
         1. Also you can check it in the parse rules by using a rule named `__schema__`, the parser will raise Error except this `__schema__` rule returns `True`.
   4.  Now to set the ParseRules of this CrawlerRule.
       1.  A valid CrawlerRule should contains `text` rule and `url` rule, and the `url` rule is optional.
       2.  Delete the existing text rule, create a new parse rule named `list`.
       3.  Create a new Parse Rule like as below: ![](https://github.com/ClericPy/watchdogs/raw/master/images/d3.png)
           1.  Here we got the list item for child rules.
       4.  Then need two child rules named `text` and `url` for the `list` rule.
       5.  Create a new parse rule named `text`  like this: ![](https://github.com/ClericPy/watchdogs/raw/master/images/d4.png)
           1.  Click the button send the `text` rule to `list` rule.
       6.  Create a new parse rule named `url` like `text`, or ignore this rule. But `$text` attribute should use `@href` for get href attribute. Also need to send this rule to `list` rule.
   5.  OK, now click `Parse` button to parse this CrawlerRule, and get the result.
   6.  Click the \<1. Save Crawler Rule\> button to save rule into database.

> Parse result

```javascript
{'Trending Python repositories on GitHub today · GitHub': {'list': {'text': 'gwen001 /      pentest-tools', 'url': 'https://github.com/gwen001/pentest-tools'}}}
```

>  CrawlerRule JSON. This JSON string can be loaded by clicking the \<Loads\> button.

```javascript
{"name":"Trending Python repositories on GitHub today · GitHub","request_args":{"method":"get","url":"https://github.com/trending/python?since=daily","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"list","chain_rules":[["css","h1.lh-condensed>a","$string"],["python","index","0"],["re","=\"/","@=\"https://github.com/"]],"child_rules":[{"name":"text","chain_rules":[["css","a","$text"],["py","index","0"],["udf","input_object.strip().replace('\\n', '')",""]],"child_rules":[],"iter_parse_child":false},{"name":"url","chain_rules":[["css","a","@href"],["python","index","0"]],"child_rules":[],"iter_parse_child":false}],"iter_parse_child":false}],"regex":"^https://github\\.com/trending/python\\?since=daily$","encoding":""}
```

# Create a Task

1. Click the \<2. Add New Task\> button.
2. Ensure the task info. ![](https://github.com/ClericPy/watchdogs/raw/master/images/d5.png)
3. Click \<Submit\> button. Create task success.

# Update a Task

1. Click \<Tasks\> tab.
2. Double click the task's row.
3. Update it, submit.
