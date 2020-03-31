"use strict";var Main={data:function(){return{activeName:"tasks",uniparser_iframe_loaded:!1,tab_new_clicked:!1,task_info_visible:!1,rule_info_visible:!1,current_host_rule:{},new_task_form:{},has_more:!0,task_list:[],current_page:0,host_list:[],visible_host_list:[],current_host:"",tag_types:["","success","info","warning","danger"],query_tasks_args:{order_by:"last_change_time",sort:"desc",tag:""},callback_workers:{},custom_links:[],custom_tabs:[],current_cb_doc:"",init_iframe_rule_json:""}},methods:{add_new_task:function(){var e=this;try{JSON.parse(this.new_task_form.result_list)}catch(e){return void this.$alert("Invalid JSON for result_list.")}try{JSON.parse(this.new_task_form.request_args)}catch(e){return void this.$alert("Invalid JSON for request_args.")}this.task_info_visible=!1;var t=JSON.stringify(this.new_task_form);this.$http.post("add_new_task",t).then(function(t){var s=t.body;"ok"==s.msg?(e.$message({message:"Update task "+e.new_task_form.name+" success: "+s.msg,type:"success"}),e.reload_tasks()):e.$message.error({message:"Update task "+e.new_task_form.name+" failed: "+s.msg,duration:0,showClose:!0})},function(t){e.$message.error({message:"connect failed: "+t.status,duration:0,showClose:!0})})},init_iframe_crawler_rule:function(e){e?this.sub_app.new_rule_json=e:/httpbin\.org\/html/g.test(this.sub_app.new_rule_json)?this.sub_app.new_rule_json='{"name":"","request_args":{"method":"get","url":"https://importpython.com/blog/feed/","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["xml","channel>item>title","$text"],["python","getitem","[0]"]],"child_rules":""},{"name":"url","chain_rules":[["xml","channel>item>link","$text"],["python","getitem","[0]"]],"child_rules":""}],"regex":"^https?://importpython.com/blog/feed/$","encoding":""}':this.sub_app.new_rule_json='{"name":"","request_args":{"method":"get","url":"http://httpbin.org/html","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["css","body h1","$text"],["python","getitem","[0]"]],"child_rules":""}],"regex":"^http://httpbin.org/html$","encoding":""}',this.sub_app.input_object="",this.sub_app.request_status="",this.sub_app.load_rule()},load_rule:function(e){this.sub_app.new_rule_json=e,this.sub_app.load_rule()},view_host_by_req:function(e){var t=JSON.parse(e).url;if(!t)return void this.$alert("request_args.url should not be null");this.current_host=new URL(t).hostname,document.getElementById("tab-rules").click(),this.task_info_visible=!1},view_crawler_rule_by_req:function(e){var t=this;if(!e)return void this.$alert("request_args should not be null");this.$http.post("find_crawler_rule",e).then(function(e){var s=e.body;if("ok"==s.msg){var r=JSON.parse(s.result);t.view_crawler_rule(r),t.task_info_visible=!1}else t.$message.error({message:"rule not find in db: "+s.msg,duration:0,showClose:!0})},function(e){t.$message.error({message:"connect failed: "+e.status,duration:0,showClose:!0})})},view_crawler_rule:function(e){this.rule_info_visible=!1,document.getElementById("tab-new").click(),this.uniparser_iframe_loaded?this.init_iframe_crawler_rule(JSON.stringify(e)):this.init_iframe_rule_json=JSON.stringify(e)},edit_crawler_rule:function(e){var t=this;this.$prompt("","Edit Crawler JSON",{confirmButtonText:"OK",cancelButtonText:"Cancel",center:!0,inputType:"textarea",closeOnClickModal:!1,inputValue:JSON.stringify(e,null,2)}).then(function(e){var s=e.value;t.process_crawler_rule("add",JSON.parse(s),0)}).catch(function(e){t.$message({type:"error",message:e})})},process_crawler_rule:function(e,t,s){var r=this,a=t||JSON.parse(this.sub_app.current_crawler_rule_json),n=JSON.stringify(a),i="crawler_rule."+e;1==s&&(i+="?force=1"),this.$http.post(i,n).then(function(s){var a=s.body;"ok"==a.msg?(r.$message({message:e+" rule success",type:"success"}),"pop"==e&&a.result&&r.show_host_rule(r.current_host_rule.host)):"add"==e&&/matched more than 1 rule/g.test(a.msg)?r.$confirm("Failed for url matched more than 1 rule, overwrite it?","Confirm",{confirmButtonText:"Yes",cancelButtonText:"No",type:"error"}).then(function(){r.process_crawler_rule(e,t,1)}).catch(function(){r.$message({type:"info",message:"Adding rule canceled."})}):r.$message.error({message:e+" rule failed: "+a.msg,duration:0,showClose:!0})},function(e){r.$message.error({message:"connect failed: "+e.status,duration:0,showClose:!0})})},show_form_add_new_task:function(e){if(e){var t="";try{t=this.sub_app.crawler_rule.name}catch(e){console.log(e)}this.new_task_form={task_id:null,name:t,enable:1,tag:"default",error:"",request_args:"",origin_url:"",interval:300,work_hours:"0, 24",max_result_count:10,result_list:"[]",custom_info:""};var s=JSON.parse(this.sub_app.current_crawler_rule_json);this.new_task_form.request_args=JSON.stringify(s.request_args),this.new_task_form.origin_url=s.request_args.url||""}this.task_info_visible=!0},change_enable:function(e){var t=this;this.$http.get("enable_task",{params:{task_id:e.task_id,enable:e.enable}}).then(function(e){var s=e.body;"ok"!=s.msg&&t.$message.error({message:"Update enable failed: "+s.msg})},function(e){t.$message.error({message:"connect failed: "+e.status})})},sort_change:function(e){this.query_tasks_args={order_by:e.column.label,sort:(e.column.order||"").replace("ending","")},this.reload_tasks()},reload_tasks:function(){this.task_list=[],this.current_page=0,this.load_tasks()},load_tasks:function(){var e=this,t=new URLSearchParams(window.location.search).get("tag");this.query_tasks_args.tag=t||"",this.$http.get("load_tasks",{params:this.query_tasks_args}).then(function(t){var s=t.body;"ok"==s.msg?(s.tasks.forEach(function(t){e.task_list.push(t)}),e.has_more=s.has_more,e.current_page+=1):(e.$message.error({message:"Loading tasks failed: "+s.msg}),e.has_more=s.has_more)},function(t){e.$message.error({message:"connect failed: "+t.status})})},load_hosts:function(){var e=this;this.$http.get("load_hosts",{params:{host:this.current_host}}).then(function(t){var s=t.body;e.current_host=s.host||"",e.host_list=s.hosts,e.visible_host_list=e.host_list},function(t){e.$message.error({message:"connect failed: "+t.status})})},init_iframe:function(){this.sub_app&&(this.init_iframe_crawler_rule(this.init_iframe_rule_json),this.init_iframe_rule_json&&(this.$message.success({message:"Rule loaded."}),this.init_iframe_rule_json=""),this.uniparser_iframe_loaded=!0)},handleClick:function(e,t){var s=this;"new"==e.name&&(this.tab_new_clicked||(this.tab_new_clicked=!0,setTimeout(function(){var e=!0,t=!1,r=void 0;try{for(var a,n=s.uni_iframe.contentWindow.document.getElementsByTagName("textarea")[Symbol.iterator]();!(e=(a=n.next()).done);e=!0){var i=a.value;i.style.height="auto",i.style.height=i.scrollHeight+"px"}}catch(e){t=!0,r=e}finally{try{!e&&n.return&&n.return()}finally{if(t)throw r}}},0))),"rules"==e.name&&this.load_hosts()},escape_html:function(e){return e?e.replace(/[&<>'"]/g,function(e){return{"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[e]||e}):""},show_time:function(e){var t='<table style="text-align: left;margin: 0 0 0 20%;font-weight: bold;">';JSON.parse(e.result_list||"[]");t+='<tr><td>last_check_time</td><td class="time-td">'+e.last_check_time.replace(/\..*/,"").replace("T"," ")+"</td></tr>",t+='<tr><td>next_check_time</td><td class="time-td">'+e.next_check_time.replace(/\..*/,"").replace("T"," ")+"</td></tr>",t+='<tr><td>last_change_time</td><td class="time-td">'+e.last_change_time.replace(/\..*/,"").replace("T"," ")+"</td></tr>",t+="</table>",this.$alert(t,"Task result list: "+e.name,{confirmButtonText:"OK",center:!0,dangerouslyUseHTMLString:!0,closeOnClickModal:!0,closeOnPressEscape:!0})},get_latest_result:function(e){var t=arguments.length>1&&void 0!==arguments[1]?arguments[1]:80;try{return JSON.parse(e).text.slice(0,t)}catch(t){return e}},show_result_list:function(e){var t=this,s="<table>";JSON.parse(e.result_list||"[]").forEach(function(e){if(result=e.result,result.url)var r='href="'+(result.url||"")+'"';else var r="";s+='<tr><td class="time-td">'+e.time+'</td><td><a target="_blank" '+r+">"+t.escape_html(result.text)+"</a></td></tr>"}),s+="</table>",this.$alert(s,"Task result list: "+e.name,{confirmButtonText:"OK",center:!0,dangerouslyUseHTMLString:!0,closeOnClickModal:!0,closeOnPressEscape:!0})},force_crawl:function(e,t){var s=this;this.$http.get("force_crawl",{params:{task_name:t.name}}).then(function(r){var a=r.body;if("ok"==a.msg){var n=a.task;Vue.set(s.task_list,e,n),n.error?s.$message.error({message:"Crawl task "+t.name+" "+n.error}):s.$message.success({message:"Crawl task "+t.name+" success"})}else s.$message.error({message:"Crawl task "+t.name+" failed: "+a.msg})},function(e){s.$message.error({message:"force_crawl connect failed: "+e.status})})},row_db_click:function(e){this.update_task(e)},show_task_error:function(e){app.$alert(e.error,"Crawler Error",{closeOnClickModal:!0,closeOnPressEscape:!0,center:!0})},update_task:function(e){this.new_task_form={task_id:e.task_id,name:e.name,enable:e.enable,tag:e.tag,request_args:e.request_args,origin_url:e.origin_url,interval:e.interval,work_hours:e.work_hours,max_result_count:e.max_result_count,result_list:e.result_list||"[]",custom_info:e.custom_info},this.show_form_add_new_task(!1)},delete_task:function(e,t){var s=this;this.$confirm("Are you sure?","Confirm",{confirmButtonText:"Delete",cancelButtonText:"Cancel",type:"warning"}).then(function(){s.$http.get("delete_task",{params:{task_id:t.task_id}}).then(function(r){var a=r.body;"ok"==a.msg?(s.$message.success({message:"Delete task "+t.name+" success"}),s.task_list.splice(e,1)):s.$message.error({message:"Delete task "+t.name+" failed: "+a.msg})},function(e){s.$message.error({message:"connect failed: "+e.status})})}).catch(function(){s.$message({type:"info",message:"Canceled"})})},delete_host_rule:function(e){var t=this;this.$confirm("Are you sure?","Confirm",{confirmButtonText:"Delete",cancelButtonText:"Cancel",type:"warning"}).then(function(){t.$http.get("delete_host_rule",{params:{host:e}}).then(function(s){var r=s.body;"ok"==r.msg?(t.$message.success({message:"Delete host "+e+" rule success"}),t.current_host_rule={},t.rule_info_visible=!1,t.load_hosts()):t.$message.error({message:"Delete host "+e+" rule failed: "+JSON.stringify(r)})},function(e){t.$message.error({message:"connect failed: "+e.status})})}).catch(function(){t.$message({type:"info",message:"Canceled"})})},show_host_rule:function(e){var t=this;this.$http.get("get_host_rule",{params:{host:e}}).then(function(s){var r=s.body;"ok"==r.msg?(t.current_host_rule=r.host_rule,t.rule_info_visible=!0):t.$message.error({message:"get_host_rule "+e+" failed: "+JSON.stringify(r)})},function(e){t.$message.error({message:"connect failed: "+e.status})})},show_work_hours_doc:function(){this.$alert("<pre><code>\nThree kinds of format:\n\n1. Tow numbers splited by ', ', as work_hours:\n0, 24           means from 00:00 ~ 23:59, for everyday\n2. JSON list of int, as work_hours:\n[1, 19]         means 01:00~01:59 a.m.  07:00~07:59 p.m. for everyday\n3. Standard strftime format, as work_days:\n> Split work_hours by '==', then check\n    if datetime.now().strftime(wh[0]) == wh[1]\n%A==Friday      means each Friday\n%m-%d==03-13    means every year 03-13\n%H==05          means everyday morning 05:00 ~ 05:59\n4. Mix up work_days and work_hours:\n> Split work_days and work_hours with ';'/'&' => 'and', '|' => 'or'.\n> Support == for equal, != for unequal.\n%w==5;20, 24        means every Friday 20:00 ~ 23:59\n[1, 2, 15];%w==5    means every Friday 1 a.m. 2 a.m. 3 p.m., the work_hours is on the left side.\n%w==5|20, 24        means every Friday or everyday 20:00 ~ 23:59\n%w==5|%w==2         means every Friday or Tuesday\n%w!=6&%w!=0         means everyday except Saturday & Sunday.\n</code></pre>","work_hours format doc",{dangerouslyUseHTMLString:!0,closeOnClickModal:!0,closeOnPressEscape:!0})},check_error_task:function(e){var t=e.row;e.rowIndex;if(t.error)return"warning-row"},click_cb_name:function(e){this.current_cb_doc=this.callback_workers[e],this.new_task_form.custom_info=e+":"},update_frequency:function(){var e=this,t=this.current_host_rule.host,s=this.current_host_rule.n||0,r=this.current_host_rule.interval||0;this.$http.get("update_host_freq",{params:{host:t,n:s,interval:r}}).then(function(a){var n=a.body;"ok"==n.msg?(e.$message({message:"Update frequency "+t+": "+n.msg,type:"success"}),e.current_host_rule.n=s,e.current_host_rule.interval=r):e.$message.error({message:"update_frequency "+t+" failed: "+JSON.stringify(n)})},function(t){e.$message.error({message:"connect failed: "+t.status})})}},watch:{current_host:function(e){var t=this;this.visible_host_list=[],/^https?:\/\//g.test(e)&&(e=new URL(e).hostname,this.current_host=e),this.host_list.forEach(function(s){s.name.includes(e)&&t.visible_host_list.push(s)})},task_info_visible:function(e){e||(this.current_cb_doc="")}},computed:{uni_iframe:function(){return document.getElementById("uni_iframe")},sub_app:function(){var e=this.uni_iframe;if(e)return e.contentWindow.app}}},vue_app=Vue.extend(Main),app=new vue_app({delimiters:["${","}"]}).$mount("#app");app.load_tasks(),function(){var e=document.getElementById("init_vars"),t=JSON.parse(e.innerHTML);Object.keys(t).forEach(function(e){app[e]=t[e]}),e.parentNode.removeChild(e)}();