var Main = {
    data() {
        return {
            activeName: "tasks",
            uniparser_iframe_loaded: false,
            task_info_visible: false,
            rule_info_visible: false,
            current_host_rule: {},
            new_task_form: {},
            has_more: true,
            task_list: [],
            current_page: 0,
            host_list: [],
            visible_host_list: [],
            current_host: "",
            tag_types: ["", "success", "info", "warning", "danger"],
            query_tasks_args: {
                order_by: "last_change_time",
                sort: "desc",
                tag: "",
            },
            callback_workers: {},
            custom_links: [],
            custom_tabs: [],
            current_cb_doc: "",
            init_iframe_rule_json: "",
            clicked_tab_names: {},
        }
    },
    methods: {
        add_new_task() {
            // {"name":"get demo","request_args":{"method":"get","url":"http://httpbin.org/get","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["css","p","$text"],["python","getitem","[0]"]],"child_rules":""}],"regex":"http://httpbin.org/get","encoding":""}
            try {
                JSON.parse(this.new_task_form.result_list)
            } catch (error) {
                this.$alert("Invalid JSON for result_list.")
                return
            }
            try {
                JSON.parse(this.new_task_form.request_args)
            } catch (error) {
                this.$alert("Invalid JSON for request_args.")
                return
            }
            this.task_info_visible = false
            let data = JSON.stringify(this.new_task_form)
            this.$http.post("add_new_task", data).then(
                (r) => {
                    var result = r.body
                    if (result.msg == "ok") {
                        this.$message({
                            message:
                                "Update task " +
                                this.new_task_form.name +
                                " success: " +
                                result.msg,
                            type: "success",
                        })
                        this.reload_tasks()
                    } else {
                        this.$message.error({
                            message:
                                "Update task " +
                                this.new_task_form.name +
                                " failed: " +
                                result.msg,
                            duration: 0,
                            showClose: true,
                        })
                    }
                },
                (r) => {
                    this.$message.error({
                        message: "connect failed: " + r.status,
                        duration: 0,
                        showClose: true,
                    })
                }
            )
        },
        init_iframe_crawler_rule(rule_json) {
            if (rule_json) {
                this.sub_app.new_rule_json = rule_json
            } else {
                if (!/httpbin\.org\/html/g.test(this.sub_app.new_rule_json)) {
                    this.sub_app.new_rule_json =
                        '{"name":"","request_args":{"method":"get","url":"http://httpbin.org/html","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["css","body h1","$text"],["python","getitem","[0]"]],"child_rules":""}],"regex":"^http://httpbin.org/html$","encoding":""}'
                } else {
                    this.sub_app.new_rule_json =
                        '{"name":"","request_args":{"method":"get","url":"https://importpython.com/blog/feed/","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["xml","channel>item>title","$text"],["python","getitem","[0]"]],"child_rules":""},{"name":"url","chain_rules":[["xml","channel>item>link","$text"],["python","getitem","[0]"]],"child_rules":""}],"regex":"^https?://importpython.com/blog/feed/$","encoding":""}'
                }
            }
            this.sub_app.input_object = ""
            this.sub_app.request_status = ""
            this.sub_app.load_rule()
        },
        load_rule(crawler_rule_json) {
            // crawler_rule_json = '{"name":"HelloWorld222","request_args":{"method":"get","url":"http://httpbin.org/forms/post","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[],"regex":"","encoding":""}'
            this.sub_app.new_rule_json = crawler_rule_json
            this.sub_app.load_rule()
        },
        view_host_by_req(request_args) {
            let url = JSON.parse(request_args).url
            if (!url) {
                this.$alert("request_args.url should not be null")
                return
            }
            // this.activeName = 'rules'
            // Vue.set(this, 'activeName', 'rules')
            document.getElementById("tab-rules").click()
            setTimeout(() => {
                this.current_host = new URL(url).hostname
            }, 0)
            this.task_info_visible = false
        },
        view_crawler_rule_by_req(request_args) {
            if (!request_args) {
                this.$alert("request_args should not be null")
                return
            }
            this.$http.post("find_crawler_rule", request_args).then(
                (r) => {
                    var result = r.body
                    if (result.msg == "ok") {
                        let rule = JSON.parse(result.result)
                        this.view_crawler_rule(rule)
                        this.task_info_visible = false
                    } else {
                        this.$message.error({
                            message: "rule not find in db: " + result.msg,
                            duration: 0,
                            showClose: true,
                        })
                    }
                },
                (r) => {
                    this.$message.error({
                        message: "connect failed: " + r.status,
                        duration: 0,
                        showClose: true,
                    })
                }
            )
        },
        view_crawler_rule(rule) {
            this.rule_info_visible = false
            document.getElementById("tab-new").click()
            if (this.uniparser_iframe_loaded) {
                this.init_iframe_crawler_rule(JSON.stringify(rule))
            } else {
                this.init_iframe_rule_json = JSON.stringify(rule)
            }
        },
        edit_crawler_rule(rule) {
            this.$prompt("", "Edit Crawler JSON", {
                confirmButtonText: "OK",
                cancelButtonText: "Cancel",
                center: true,
                inputType: "textarea",
                closeOnClickModal: false,
                inputValue: JSON.stringify(rule, null, 2),
            })
                .then(({ value }) => {
                    this.process_crawler_rule("add", JSON.parse(value), 0)
                })
                .catch((err) => {
                    this.$message({
                        type: "error",
                        message: err,
                    })
                })
        },
        process_crawler_rule(method, rule, force) {
            let current_crawler_rule =
                rule || JSON.parse(this.sub_app.current_crawler_rule_json)
            let data = JSON.stringify(current_crawler_rule)
            let api = "crawler_rule." + method
            if (force == 1) {
                api += "?force=1"
            }
            this.$http.post(api, data).then(
                (r) => {
                    var result = r.body
                    if (result.msg == "ok") {
                        this.$message({
                            message: method + " rule success",
                            type: "success",
                        })
                        if (method == "pop" && result.result) {
                            this.show_host_rule(this.current_host_rule.host)
                        }
                    } else {
                        if (
                            method == "add" &&
                            /matched more than 1 rule/g.test(result.msg)
                        ) {
                            this.$confirm(
                                "Failed for url matched more than 1 rule, overwrite it?",
                                "Confirm",
                                {
                                    confirmButtonText: "Yes",
                                    cancelButtonText: "No",
                                    type: "error",
                                }
                            )
                                .then(() => {
                                    this.process_crawler_rule(method, rule, 1)
                                })
                                .catch(() => {
                                    this.$message({
                                        type: "info",
                                        message: "Adding rule canceled.",
                                    })
                                })
                        } else {
                            this.$message.error({
                                message: method + " rule failed: " + result.msg,
                                duration: 0,
                                showClose: true,
                            })
                        }
                    }
                },
                (r) => {
                    this.$message.error({
                        message: "connect failed: " + r.status,
                        duration: 0,
                        showClose: true,
                    })
                }
            )
        },
        show_form_add_new_task(create_new_task) {
            if (create_new_task) {
                let init_name = ""
                try {
                    init_name = this.sub_app.crawler_rule.name
                } catch (error) {
                    console.log(error)
                }
                this.new_task_form = {
                    task_id: null,
                    name: init_name,
                    enable: 1,
                    tag: "default",
                    error: "",
                    request_args: "",
                    origin_url: "",
                    interval: 300,
                    work_hours: "0, 24",
                    max_result_count: 10,
                    result_list: "[]",
                    custom_info: "",
                }
                let current_crawler_rule = JSON.parse(
                    this.sub_app.current_crawler_rule_json
                )
                this.new_task_form.request_args = JSON.stringify(
                    current_crawler_rule.request_args
                )
                this.new_task_form.origin_url =
                    current_crawler_rule.request_args.url || ""
            }
            this.task_info_visible = true
        },
        change_enable(row) {
            this.$http
                .get("enable_task", {
                    params: {
                        task_id: row.task_id,
                        enable: row.enable,
                    },
                })
                .then(
                    (r) => {
                        var result = r.body
                        if (result.msg != "ok") {
                            this.$message.error({
                                message: "Update enable failed: " + result.msg,
                            })
                        }
                    },
                    (r) => {
                        this.$message.error({
                            message: "connect failed: " + r.status,
                        })
                    }
                )
        },
        sort_change(col) {
            this.query_tasks_args = {
                order_by: col.column.label,
                sort: (col.column.order || "").replace("ending", ""),
            }
            this.reload_tasks()
        },
        reload_tasks() {
            this.task_list = []
            this.current_page = 0
            this.load_tasks()
        },
        load_tasks() {
            let tag = new URLSearchParams(window.location.search).get("tag")
            if (tag) {
                this.query_tasks_args["tag"] = tag
            } else {
                this.query_tasks_args["tag"] = ""
            }
            this.current_page += 1
            this.query_tasks_args["page"] = this.current_page
            this.$http
                .get("load_tasks", {
                    params: this.query_tasks_args,
                })
                .then(
                    (r) => {
                        var result = r.body
                        if (result.msg == "ok") {
                            result.tasks.forEach((item) => {
                                this.task_list.push(item)
                            })
                            this.has_more = result.has_more
                        } else {
                            this.$message.error({
                                message: "Loading tasks failed: " + result.msg,
                            })
                            this.has_more = result.has_more
                            this.current_page -= 1
                        }
                    },
                    (r) => {
                        this.current_page -= 1
                        this.$message.error({
                            message: "connect failed: " + r.status,
                        })
                    }
                )
        },
        load_hosts() {
            // (this.current_host)
            this.$http
                .get("load_hosts", {
                    params: {
                        host: this.current_host,
                    },
                })
                .then(
                    (r) => {
                        var result = r.body
                        this.current_host = result.host || ""
                        this.host_list = result.hosts
                        this.visible_host_list = this.host_list
                    },
                    (r) => {
                        this.$message.error({
                            message: "connect failed: " + r.status,
                        })
                    }
                )
        },
        init_iframe() {
            if (this.sub_app) {
                this.init_iframe_crawler_rule(this.init_iframe_rule_json)
                if (this.init_iframe_rule_json) {
                    this.$message.success({
                        message: "Rule loaded.",
                    })
                    this.init_iframe_rule_json = ""
                }
                this.uniparser_iframe_loaded = true
            }
        },
        handleClick(tab) {
            // init tabs
            if (!(tab.name in this.clicked_tab_names)) {
                // handle click event, which is clicked at the first time
                this.clicked_tab_names[tab.name] = 1
                // if (tab.name == 'new') {
                //     // for autosize bug in iframe if not seen
                //     setTimeout(() => {
                //         for (const text of this.uni_iframe.contentWindow.document
                //                 .getElementsByTagName(
                //                     'textarea')) {
                //             text.style.height = 'auto';
                //             text.style.height = text.scrollHeight + 'px';
                //         };
                //     }, 0);
                // }
                if (tab.name == "rules") {
                    this.load_hosts()
                }
            }
        },
        escape_html(string) {
            if (!string) {
                return ""
            }
            return string.replace(
                /[&<>'"]/g,
                (tag) =>
                    ({
                        "&": "&amp;",
                        "<": "&lt;",
                        ">": "&gt;",
                        "'": "&#39;",
                        '"': "&quot;",
                    }[tag] || tag)
            )
        },
        show_time(row) {
            var text =
                '<table style="text-align: left;margin: 0 0 0 20%;font-weight: bold;">'
            var items = JSON.parse(row.result_list || "[]")
            text +=
                '<tr><td>last_check_time</td><td class="time-td">' +
                row.last_check_time.replace(/\..*/, "").replace("T", " ") +
                "</td></tr>"
            text +=
                '<tr><td>next_check_time</td><td class="time-td">' +
                row.next_check_time.replace(/\..*/, "").replace("T", " ") +
                "</td></tr>"
            text +=
                '<tr><td>last_change_time</td><td class="time-td">' +
                row.last_change_time.replace(/\..*/, "").replace("T", " ") +
                "</td></tr>"
            text += "</table>"
            this.$alert(text, "Task result list: " + row.name, {
                confirmButtonText: "OK",
                center: true,
                dangerouslyUseHTMLString: true,
                closeOnClickModal: true,
                closeOnPressEscape: true,
            })
        },
        get_latest_result(latest_result, max_length = 80) {
            try {
                let item = JSON.parse(latest_result)
                return item.title || item.text.slice(0, max_length)
            } catch (error) {
                return latest_result
            }
        },
        show_result_list(row) {
            var text = "<table>"
            var items = JSON.parse(row.result_list || "[]")
            items.forEach((item) => {
                result = item.result
                if (result.url) {
                    var href = 'href="' + (result.url || "") + '"'
                } else {
                    var href = ""
                }
                text +=
                    '<tr><td class="time-td">' +
                    item.time +
                    '</td><td><a target="_blank" ' +
                    href +
                    ">" +
                    this.escape_html(result.title || result.text) +
                    "</a></td></tr>"
            })
            text += "</table>"
            this.$alert(text, "Task result list: " + row.name, {
                confirmButtonText: "OK",
                center: true,
                dangerouslyUseHTMLString: true,
                closeOnClickModal: true,
                closeOnPressEscape: true,
            })
        },
        force_crawl(index, row) {
            this.$http
                .get("force_crawl", {
                    params: {
                        task_name: row.name,
                    },
                })
                .then(
                    (r) => {
                        var result = r.body
                        if (result.msg == "ok") {
                            let task = result.task
                            Vue.set(this.task_list, index, task)
                            if (task.error) {
                                this.$message.error({
                                    message:
                                        "Crawl task " +
                                        row.name +
                                        " " +
                                        task.error,
                                })
                            } else {
                                this.$message.success({
                                    message:
                                        "Crawl task " + row.name + " success",
                                })
                            }
                        } else {
                            this.$message.error({
                                message:
                                    "Crawl task " +
                                    row.name +
                                    " failed: " +
                                    result.msg,
                            })
                        }
                    },
                    (r) => {
                        this.$message.error({
                            message: "force_crawl connect failed: " + r.status,
                        })
                    }
                )
        },
        row_db_click(row) {
            this.update_task(row)
        },
        show_task_error(row) {
            app.$alert(row.error, "Crawler Error", {
                closeOnClickModal: true,
                closeOnPressEscape: true,
                center: true,
            })
        },
        update_task(row) {
            this.new_task_form = {
                task_id: row.task_id,
                name: row.name,
                enable: row.enable,
                tag: row.tag,
                request_args: row.request_args,
                origin_url: row.origin_url,
                interval: row.interval,
                work_hours: row.work_hours,
                max_result_count: row.max_result_count,
                result_list: row.result_list || "[]",
                custom_info: row.custom_info,
            }
            this.show_form_add_new_task(false)
        },
        delete_task(index, row) {
            this.$confirm("Are you sure?", "Confirm", {
                confirmButtonText: "Delete",
                cancelButtonText: "Cancel",
                type: "warning",
            })
                .then(() => {
                    this.$http
                        .get("delete_task", {
                            params: {
                                task_id: row.task_id,
                            },
                        })
                        .then(
                            (r) => {
                                var result = r.body
                                if (result.msg == "ok") {
                                    this.$message.success({
                                        message:
                                            "Delete task " +
                                            row.name +
                                            " success",
                                    })
                                    this.task_list.splice(index, 1)
                                } else {
                                    this.$message.error({
                                        message:
                                            "Delete task " +
                                            row.name +
                                            " failed: " +
                                            result.msg,
                                    })
                                }
                            },
                            (r) => {
                                this.$message.error({
                                    message: "connect failed: " + r.status,
                                })
                            }
                        )
                })
                .catch(() => {
                    this.$message({
                        type: "info",
                        message: "Canceled",
                    })
                })
        },
        delete_host_rule(host) {
            this.$confirm("Are you sure?", "Confirm", {
                confirmButtonText: "Delete",
                cancelButtonText: "Cancel",
                type: "warning",
            })
                .then(() => {
                    this.$http
                        .get("delete_host_rule", {
                            params: {
                                host: host,
                            },
                        })
                        .then(
                            (r) => {
                                var result = r.body
                                if (result.msg == "ok") {
                                    this.$message.success({
                                        message:
                                            "Delete host " +
                                            host +
                                            " rule success",
                                    })
                                    this.current_host_rule = {}
                                    this.rule_info_visible = false
                                    this.load_hosts()
                                } else {
                                    this.$message.error({
                                        message:
                                            "Delete host " +
                                            host +
                                            " rule failed: " +
                                            JSON.stringify(result),
                                    })
                                }
                            },
                            (r) => {
                                this.$message.error({
                                    message: "connect failed: " + r.status,
                                })
                            }
                        )
                })
                .catch(() => {
                    this.$message({
                        type: "info",
                        message: "Canceled",
                    })
                })
        },
        show_host_rule(host) {
            this.$http
                .get("get_host_rule", {
                    params: {
                        host: host,
                    },
                })
                .then(
                    (r) => {
                        var result = r.body
                        if (result.msg == "ok") {
                            this.current_host_rule = result.host_rule
                            this.rule_info_visible = true
                        } else {
                            this.$message.error({
                                message:
                                    "get_host_rule " +
                                    host +
                                    " failed: " +
                                    JSON.stringify(result),
                            })
                        }
                    },
                    (r) => {
                        this.$message.error({
                            message: "connect failed: " + r.status,
                        })
                    }
                )
        },
        show_work_hours_doc() {
            let html = `<pre><code>${this.work_hours_doc}</code></pre>`
            this.$alert(html, "work_hours format doc", {
                dangerouslyUseHTMLString: true,
                closeOnClickModal: true,
                closeOnPressEscape: true,
                customClass: "work_hours_doc",
            })
        },
        check_error_task({ row, rowIndex }) {
            if (row.error) {
                return "warning-row"
            }
        },
        click_cb_name(name) {
            this.current_cb_doc = this.callback_workers[name]
            this.new_task_form.custom_info = name + ":"
        },
        update_frequency() {
            let host = this.current_host_rule.host
            let n = this.current_host_rule.n || 0
            let interval = this.current_host_rule.interval || 0
            this.$http
                .get("update_host_freq", {
                    params: {
                        host: host,
                        n: n,
                        interval: interval,
                    },
                })
                .then(
                    (r) => {
                        var result = r.body
                        if (result.msg == "ok") {
                            this.$message({
                                message:
                                    "Update frequency " +
                                    host +
                                    ": " +
                                    result.msg,
                                type: "success",
                            })
                            this.current_host_rule.n = n
                            this.current_host_rule.interval = interval
                        } else {
                            this.$message.error({
                                message:
                                    "update_frequency " +
                                    host +
                                    " failed: " +
                                    JSON.stringify(result),
                            })
                        }
                    },
                    (r) => {
                        this.$message.error({
                            message: "connect failed: " + r.status,
                        })
                    }
                )
        },
    },
    watch: {
        current_host: function (val) {
            this.visible_host_list = []
            if (/^https?:\/\//g.test(val)) {
                val = new URL(val).hostname
                this.current_host = val
            }
            this.host_list.forEach((host) => {
                if (host.name.includes(val)) {
                    this.visible_host_list.push(host)
                }
            })
        },
        task_info_visible: function (val) {
            if (!val) {
                this.current_cb_doc = ""
            }
        },
    },
    computed: {
        uni_iframe() {
            return document.getElementById("uni_iframe")
        },
        sub_app() {
            // return this.$refs.iframe.contentWindow.window.app
            let uni = this.uni_iframe
            if (uni) {
                return uni.contentWindow.app
            }
        },
    },
}
var vue_app = Vue.extend(Main)
var app = new vue_app({
    delimiters: ["${", "}"],
}).$mount("#app")
// app.load_tasks()
// init app vars
;(() => {
    // init_vars
    let node = document.getElementById("init_vars")
    let args = JSON.parse(window.atob(node.innerHTML))
    Object.keys(args).forEach((name) => {
        app[name] = args[name]
    })
    node.parentNode.removeChild(node)
    // auto load
    var io = new IntersectionObserver((entries) => {
        if (entries[0].intersectionRatio <= 0) return
        if (app.has_more) {
            app.load_tasks()
        }
    })
    io.observe(document.getElementById("auto_load"))
})()
