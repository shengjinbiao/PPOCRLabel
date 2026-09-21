

var protocol = location.protocol;
var host = location.host;
var http_url = protocol + "//" + host;

$(document).ready(function () {

    pageLayout();

    //窗口改变时布局
    $(window).resize(function () {
        pageLayout();
    })

    function pageLayout() {
        //获取当前浏览器宽高
        var currentPageWidth = $(window).width();
        var currentPageHeight = $(window).height();
        //浏览器宽限制最小1300
        if (currentPageWidth < 1300) {
            currentPageWidth = 1300;
        }
        //浏览器高限制最小800
        if (currentPageHeight < 800) {
            currentPageHeight = 800;
        }
        //设置body样式适应浏览器
        $("body").css({
            "width": currentPageWidth + "px",
            "height": currentPageHeight + "px"
        })
        //跟据浏览器height的改变，改变主要元素布局，menu_bar为左侧导航栏，right_area为右侧区域，包含jgw_font_content以及顶部按部首展示div,jgw_font_content为甲骨字展示部分
        $(".menu_bar").css("height", currentPageHeight - 65 + "px");
        $(".right_area").css("height", currentPageHeight - 65 + "px");
        $(".jgw_font_content").css("height", currentPageHeight - 127 + "px");
        $(".retrieve_result").css("height", currentPageHeight - 127 + "px");
    }

    ishaveRight(); //是否有权限更新
    numHtml(); //统计字形
    bsHtml(); //主视窗部首页面
    viewHtml(); // 浏览量
    $("#zhulu").attr("href", "/home/zl/index.html");
    $("#wenxian").attr("href", "/home/wx/index.html");
	var params = new URLSearchParams(window.location.search)
	let value = params.get('value')
	console.log(value)
	if (value) {
		console.log(params.get('type'))
		let retrieveCon = $(".retrieve_con a")[params.get('type')];
		$("#radical_t").css({ "background": "#ffffff", "color": "#2d9bff" });
		$("#radical_t").parent('a').removeClass("cur");
		retrieveCon.click();
		$('.retrieve_input').val(unescape(value));
		setTimeout(()=>{
			$('.retrieve_btn').click();
		},1)
	}
})

//判断权限
function ishaveRight() {
    $.getJSON("method/userData.ashx?groupId=5", function (data, state, xhr) {
        if (state == "success") {
            if (data != "no") {
                if (data.user[0].USERNAME == "ANONY") {
                    debugger;
                    $("#update").hide();
                    $("#denglu").attr("href", "/home/account/index.html?type=login&returnUrl=" + encodeURIComponent("/home/zx/index.html"));
                    $("#zhuxiao").hide();
                } else {
                    if (data.result == "yes") {
                        $("#update").show().css("display", "inline-block");
                    }
                    $("#denglu").attr("href", "javascript:void(0)").text(data.user[0].USERNAME + "  您好！");
                    $("#zhuxiao").show();
                }
            } else {
                $("#denglu").attr("href", "/home/account/index.html?type=login&returnUrl=" + encodeURIComponent("/home/zx/index.html"));
                $("#zhuxiao").hide();
            }
        }
    });
}

//统计字形
function numHtml() {
    $.getJSON("method/jgwzx.ashx?type=fontnum", function (data, state, xhr) {
        if (state = "success") {
            $("#dz").text(data.DZNUM);
            $("#zx").text(data.ZXNUM);
        }
    })
}

function viewHtml() {
    $.getJSON("method/jgwzx.ashx?type=viewnum", function (data, state, xhr) {
        if (state = "success") {
            $("#search").text(data.search);
            $("#view").text(data.browser);
        }
    })
}
 
//部首表点击事件
$("#radical_t").click(function () {
    bsHtml();
	// $('.bgc-box').show();
    // $('.jgw_font_content').css("border-radius", "0 8px 8px 8px");
	$('.retrieve_input').val("");
	$('.retrieve').css({"visibility":"hidden","margin-bottom":"0px"});
	$(".retrieve_con a").removeClass("cur");
	$(this).parent().parent().siblings('.sort_area').find('a').removeClass('cur'); 
	$(this).parent().addClass("cur");
})

//部首html拼接
function bsHtml() {

    $(".jgw_font_content").html("<img src='images/loading.gif' class='loadimage'>");

    var radical_html = "";
    var else_html = "";
    $.getJSON("method/jgwbs.ashx", function (data, state, xhr) {

        if (state = "success") {
             var str_173 = "";
            var str_174 = "";
            var str_175 = "";
            var str_176 = "";
            var str_177 = "";
            var str_178 = "";
            var str_179 = "";
            var str_200 = "";
            for (var i = 0; i < data.length; i++) {
                var code = data[i].BSBM.replace("U", "").toUpperCase();
                if (code == "7-173") {
                    code = code.replace("7-", "");
                    str_173 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;' data-number=0 data-radical='" + code + "'>难检字</div>"
                } else if (code == "7-174") {
                    code = code.replace("7-", "");
                    str_174 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>数字</div>"
                } else if (code == "7-175") {
                    code = code.replace("7-", "");
                    str_175 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>干支</div>"
                } else if (code == "7-176") {
                    code = code.replace("7-", "");
                    str_176 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>合文祖先</div>"
                } else if (code == "7-177") {
                    code = code.replace("7-", "");
                    str_177 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>月份</div>"
                } else if (code == "7-178") {
                    code = code.replace("7-", "");
                    str_178 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>其他合文</div>"
                } else if (code == "7-179") {
                    code = code.replace("7-", "");
                    str_179 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>数字其他</div>"
                } else if (code == "7-200") {
                    code = code.replace("7-", "");
                    str_200 = "<div class='radical_table_div' style='font-size: 14px;line-height: 45px;'  data-number=0 data-radical='" + code + "'>残疑字</div>"
                } else {
                    var intCode = parseInt(code, 16);
                    try {
                        var zhuanhuan_radical = String.fromCodePoint(intCode);
                        if (code == "500AD" || code == "500AE" || code == "500AF" || code == "500B0" || code == "500B1" || code == "60055" || code == "60053" || code == "600A9") {
                        } else {
                            radical_html += "<div class='radical_table_div' data-number=0 data-radical='" + code + "'>" + zhuanhuan_radical + "</div>";
                        }
                    } catch (ex) {
                        console.log(code);
                    }
                }
            }
        }
        radical_html += else_html;
        radical_html += str_173;
        radical_html += str_200;
        radical_html += str_175;
        radical_html += str_174;
        radical_html += str_177;
        radical_html += str_179;
        radical_html += str_176;
        radical_html += str_178;
        $(".jgw_font_content").html(radical_html);
        $(".pagenav").hide();
    });

    //导航按钮变色
    $("#radical_t").css({ "background": "#2d9bff", "color": "#ffffff" });
    $("#all_font").css({ "background": "#ffffff", "color": "#2d9bff" });
    $("#all_zx").css({ "background": "#ffffff", "color": "#2d9bff" });
}

//点击部首事件
$(".jgw_font_content").delegate(".radical_table_div", "click", function () {
    click_radical_table($(this));
})

//显示部首查字面板
function click_radical_table(e) {

    var code = "" + e.attr("data-radical"); //部首编码
    var current_number = parseInt(e.attr("data-number"));

    if (current_number == 0) { //显示选择的部首组合
        var c_radical = "";
        if (code == "173" || code == "174" || code == "175" || code == "176" || code == "177" || code == "178" || code == "179" || code == "200") {
            c_radical = "<div class='radical_show_number' data-id='" + code + "' data-number=" + 1 + "><img src='img/img_" + code + ".jpg' alt='image' /><sup>" + 1 + "</sup></div>";
        } else {
            var zhuanhuan_radical = String.fromCodePoint(parseInt(code, 16));
            c_radical = "<div class='radical_show_number' data-id='" + code + "' data-number=" + 1 + ">" + zhuanhuan_radical + "<sup>" + 1 + "</sup></div>"
        }
        $(".radical_select_list").append(c_radical);
    } else {
        $(".radical_show_number[data-id='" + code + "']").find("sup").html(current_number + 1)
        $(".radical_show_number[data-id='" + code + "']").attr("data-number", current_number + 1)
    }

    current_number++; //再次选择
    e.attr("data-number", current_number)

    if ($(".radical_show_number").length >= 1) {
        var select = [];
        $(".radical_show_number").each(function () {
            var number = $(this).find("sup").html();
            for (var i = 0; i < number; i++) {
                select.push("U" + $(this).attr("data-id"));
            }
        })
        searZxByBs(select);  
    }
}

//部首查字
function searZxByBs(select) {

    var html = "";
    jQuery.getJSON("method/jgwzx.ashx?bm=" + select + "&type=searchbybs", function (data, state, xhr) {
        if (state = "success") {
            debugger;
            if (data.length > 0) {
                for (var i = 0; i < data.length; i++) {
                    var fanti = data[i].FTZ;
                    var zkbm = data[i].ZKBM.replace("U", "");
					try{
						var zhuanhuan = String.fromCodePoint(parseInt(zkbm, 16));
					}catch(e){
						continue;
					} 
                    //正则匹配去除简体中数字以及,，.。
                    if (fanti.length > 1) {
                        var regex = new RegExp("[0-9,，.。(暂无)]", "g")
                        fanti = fanti.replace(regex, "")
                    }

                    html += "<div class='jgw_font_show' title='" + fanti + "' data-fontid='" + zkbm + "'><span class='yuan_jgw'>" + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                }
            } else {
                html += "<span style='float:unset;width:unset'>暂无数据！<span>"
            }
        }
        $(".radical_init").html(html);
    });
    $(".jgw_radical_content").show();
}

//清空部首事件
$(".re_radical").click(function () {
    $(".radical_select_list").html("");
    $(".radical_table_div").each(function () {
        $(this).attr("data-number", "0");
    });
});

//部首查字面板关闭
$(".bssr_close").click(function () {

    $(".radical_table_div").each(function () {
        $(this).attr("data-number", "0");
    });
    $(".radical_select_list ").html("");
    $(".radical_init").html("");
    $(".jgw_radical_content ").hide();
})
 
//总单字点击事件
$("#all_font").click(function () {
    $("#type").val("sortzxbybs");
    $(".pagenav").show();
    $("#radical_t").css({ "background": "#ffffff", "color": "#2d9bff" });
    $("#all_zx").css({ "background": "#ffffff", "color": "#2d9bff" });
    $("#all_font").css({ "background": "#2d9bff", "color": "#ffffff" });
	// $('.bgc-box').hide();
    // $('.jgw_font_content').css( "border-radius", "8px" );
	$('.retrieve_input').val(""); 
	$('.retrieve').css({"visibility":"hidden","margin-bottom":"0px"});
	$(".retrieve_con a").removeClass("cur");
	$(this).parent().addClass("cur").siblings("a").removeClass("cur");
    $(this).parent().parent(".sort_area").siblings(".sort_area").find("a").removeClass("cur");
    loadAllDz("1");
})

var pageListNum = []
//分页点击事件
function searchPageNew(page) { 
	$("#inputgo").val(page); 
	if(page > pageListNum){
		$("#inputgo").val(pageListNum);
	}
	if(page == 0){
		$("#inputgo").val(1);
	}
    var type = $("#type").val();
    if (type == "sortzxbybs") {
        if (parseInt(page) <= 0) {
            loadAllDz(1);
        } else if (parseInt(page) > parseInt($("#pagecount").val())) {
            loadAllDz(parseInt($("#pagecount").val()));
        } else {
            loadAllDz(page);
        }
    } else {
        if (parseInt(page) <= 0) {
            loadAllZx(1);
        } else if (parseInt(page) > parseInt($("#pagecount").val())) {
            loadAllZx(parseInt($("#pagecount").val()));
        } else {
            loadAllZx(page);
        }
    }
}

//点击跳转事件
$("#iconfontGO").click(function () {
	iconfontGOEvent()
});

	
function iconfontGOEvent(){
	var pageinput = $("#inputgo").val();
	console.log($("#inputgo").val())
	console.log(pageListNum)
	
	searchPageNew(pageinput);
	
	if( pageinput > pageListNum){
		$("#inputgo").val(20);
	}
}

$(document).ready(function() {  
    $('#inputgo').keydown(function(event) {  
        if (event.keyCode == 13) {  
            event.preventDefault(); // 阻止默认的回车行为，比如表单提交  
            iconfontGOEvent()
        }  
    });  
});

var elseHtml = "";
//加载总单字数据
function loadAllDz(page) {

    $(".jgw_font_content").html("<img src='images/loading.gif' class='loadimage'>");

    var fontHtml = "";

    $.getJSON("method/jgwzx.ashx?type=sortzxbybs&pageindex=" + page, function (data, state, xhr) {
        if (state = "success") {
            var pageList = data.pageList[0];
			pageListNum = data.pageList[0].sumpage;
			console.log(pageListNum)
            var font = data.ALLDZ;
            //加载部首
            for (var i = 0; i < font.length; i++) {

                var zx = font[i].JGWZX;
                var bsCode = font[i].BSBM.replace("U", "");

                if (bsCode == "173" || bsCode == "174" || bsCode == "175" || bsCode == "176") {
                    elseHtml += "<div class='radical_sort' data-radical='" + bsCode + "'><img class='radcial_head' src='images/img_" + bsCode + ".jpg' />"
                } else {
                    var intBsCode = parseInt(bsCode, 16);
                    try {
                        var zhuanhuan_radical = String.fromCodePoint(intBsCode);
                    } catch (ex) {
                        console.log(intBsCode);
                    }
                    fontHtml += "<div class='radical_sort' data-radical='" + bsCode + "'><div class='radcial_head'>" + zhuanhuan_radical + "</div>";
                }

                //加载部首下的字形
                if (zx.length > 0) {
                    for (var j = 0; j < zx.length; j++) {

                        var code = zx[j].ZKBM.replace("U", "")
                        var zxCode = parseInt(code, 16);
                                   try {
                            var zhuanhuan = String.fromCodePoint(zxCode);//编码转换为甲骨字
                        } catch (ex) {
                            console.log(intBsCode);
                        }
                        var fanti = zx[j].FTZ;//得到甲骨字的繁体

                        //正则匹配去除简体中杂项
                        if (fanti.length > 1) {
                            var regex = new RegExp("[0-9,，.。(暂无)]", "g")
                            fanti = fanti.replace(regex, "")
                        }
                        if (bsCode == "173" || bsCode == "174" || bsCode == "175" || bsCode == "176") {
                            elseHtml += "<div class='jgw_font_show' title='"
                                + fanti + "' data-fontid='" + code + "'><span class='yuan_jgw'>"
                                + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                        } else {
                            fontHtml += "<div class='jgw_font_show' title='"
                                + fanti + "' data-fontid='" + code + "'><span class='yuan_jgw'>"
                                + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                        }
                    }
                }
                if (bsCode == "173" || bsCode == "174" || bsCode == "175" || bsCode == "176") {
                    elseHtml += "</div>";
                } else {
                    fontHtml += "</div>";
                }
            }
            loadPage(pageList); //加载分页
            if (page == 18) {
                debugger;
                $(".jgw_font_content").html(fontHtml + elseHtml);
            } else {
                $(".jgw_font_content").html(fontHtml);
            }
        }
    })
}

//加载分页
function loadPage(pageList) {
    var pageHtml = "";
    var pags = pageList.pages;
    var pageArray = pags.split(",");
    for (var p = 0; p < pageArray.length; p++) {
        if (pageArray[p] != 0) {
            if (pageArray[p] == pageList.curpage) {
                pageHtml += "<a href='javascript:void(0);' class='active' onclick=searchPageNew(" + pageArray[p].replace("\'", "") + ")>" + pageArray[p].replace("\'", "") + "</a>";
            } else {
                pageHtml += "<a href='javascript: void (0);' onclick=searchPageNew(" + pageArray[p].replace("\'", "") + ")>" + pageArray[p].replace("\'", "") + "</a>";
            }
        } else {
            pageHtml += "<i class='iconfont icon-dian2'>......</i>";
        }
    }
    $("#pageList").html(pageHtml);
    $("#pageindex").val(pageList.curpage);
    $("#pagecount").val(pageList.sumpage);
    $(".page-next").attr("onclick", "searchPageNew(" + (parseInt(pageList.curpage) + 1) + ")");
    $(".page-prev").attr("onclick", "searchPageNew(" + (parseInt(pageList.curpage) - 1) + ")");
}

//总单字甲骨字点击事件
$(".jgw_font_content").on("click", ".jgw_font_show", function () {
    getFontObject($(this));
})

//从属字点击事件
$(".yixingti_content").on("click", ".congshu_content_font", function () {
    yxtTo($(this));
})

//从属字点击事件
$(".xiangguanzx_content").on("click", ".xiangguan_content_font", function () {
    yxtTo($(this));
})

//部首查字甲骨字点击事件
$(".radical_init").on("click", ".jgw_font_show", function () {
    getFontObject($(this));
})


function tounicode(data) {

    var str = '';
    for (var i = 0; i < data.length; i++) {
        str += "\\u" + parseInt(data[i].charCodeAt(0), 10).toString(16);
    }
    return str;
}

//点击该字，得到该字的json对象
function getFontObject(event) {
    var _this = event
    // $(".jgw_font_show").css("border", "solid 1px #b9b9b9")
    // event.css("border", "solid 1px red")
    debugger;
    // var currentX = _this.offset().left
    // var currentY = _this.offset().top
	var currentX = '50%'
	var currentY = '50%'
    var currentCode = _this.attr("data-fontid"); //字库编码
    var Ucode = "U" + currentCode;
    currentCode = Ucode.toUpperCase()
    var fontObject;
    jQuery.getJSON("method/jgwzx.ashx?bm=" + currentCode + "&type=getzxbybm", function (data, state, xhr) {
        if (state = "success") {
            fontObject = data;
            //构造字体详细信息面板，currentX和currentY作为点击后面板出现对应的坐标
            clickFont(fontObject, currentX, currentY)
        }
    })
}
 
//总字形点击事件
$("#all_zx").click(function () {

    $("#type").val("sortallbybs");
    $(".pagenav").show();
    $("#radical_t").css({ "background": "#ffffff", "color": "#2d9bff" });
    $("#all_font").css({ "background": "#ffffff", "color": "#2d9bff" });
    $("#all_zx").css({ "background": "#2d9bff", "color": "#ffffff" });
	// $('.bgc-box').hide();
    // $('.jgw_font_content').css("border-radius", "8px");
	$('.retrieve_input').val("");
	$('.retrieve').css({"visibility":"hidden","margin-bottom":"0px"});
	$(".retrieve_con a").removeClass("cur");
	$(this).parent().addClass("cur").siblings("a").removeClass("cur");
    $(this).parent().parent(".sort_area").siblings(".sort_area").find("a").removeClass("cur");
    loadAllZx("1");
})

//加载字形数据
var allelsehtml = "";
function loadAllZx(page) {
    $(".jgw_font_content").html("<img src='images/loading.gif' class='loadimage'>");

    var fontHtml = "";
    $.getJSON("method/jgwzx.ashx?type=sortallbybs&pageindex=" + page, function (data, state, xhr) {
        if (state = "success") {
            var pageList = data.pageList[0];
			pageListNum = data.pageList[0].sumpage;
            var font = data.ALLDZ;
            //加载部首
            for (var i = 0; i < font.length; i++) {
                var zx = font[i].JGWZX;
                var bsCode = font[i].BSBM.replace("U", "");

                if (bsCode == "173" || bsCode == "174" || bsCode == "175" || bsCode == "176") {
                    allelsehtml += "<div class='radical_sort' data-radical='" + bsCode + "'><img class='radcial_head' src='img/img_" + bsCode + ".jpg' />"
                } else {
                    var intBsCode = parseInt(bsCode, 16);
                    var zhuanhuan_radical = String.fromCodePoint(intBsCode);
                    fontHtml += "<div class='radical_sort' data-radical='" + bsCode + "'><div class='radcial_head'>" + zhuanhuan_radical + "</div>";
                }

                //加载部首下的字形
                if (zx.length > 0) {
                    for (var j = 0; j < zx.length; j++) {

                        var code = zx[j].ZKBM.replace("U", "")
                        var zxCode = parseInt(code, 16);
                        try {
                            var zhuanhuan = String.fromCodePoint(zxCode);//编码转换为甲骨字
                        } catch (ex) {
                            console.log(intBsCode);
                        }
                        var fanti = zx[j].FTZ;//得到甲骨字的繁体

                        //正则匹配去除简体中杂项
                        if (fanti.length > 1) {
                            var regex = new RegExp("[0-9,，.。(暂无)]", "g")
                            fanti = fanti.replace(regex, "")
                        }
                        if (bsCode == "173" || bsCode == "174" || bsCode == "175" || bsCode == "176") {
                            allelsehtml += "<div class='jgw_font_show' title='"
                                + fanti + "' data-fontid='" + code + "'><span class='yuan_jgw'>"
                                + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                        } else {
                            fontHtml += "<div class='jgw_font_show' title='"
                                + fanti + "' data-fontid='" + code + "'><span class='yuan_jgw'>"
                                + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                        }
                    }
                }
                fontHtml += "</div>";
            }

            loadPage(pageList); //加载分页
            if (page == 18) {
                debugger;
                $(".jgw_font_content").html(fontHtml + allelsehtml);
            } else {
                $(".jgw_font_content").html(fontHtml);
            }
        }
    })
}
    

//异形字点击事件
function yxtTo(e) {
    var _this = e
    //_this.css("border", "solid 1px #b9b9b9");
    // _this.css("border", "solid 1px red");
    debugger;
    //var parent = _this.parent().parent().parent().offset().left;
    var currentX = _this.parent().parent().parent().offset().left;
    var currentY = _this.parent().parent().parent().offset().top;
    var currentCode = _this.attr("data-code")
    var Ucode = "U" + currentCode;
    currentCode = Ucode.toUpperCase();
    var fontObject;
    //遍历字体信息，得到该字的json对象
    jQuery.getJSON("method/jgwzx.ashx?dbCode=JGWZX&bm=" + currentCode + "&type=1", function (data, state, xhr) {
        if (state = "success") {
            debugger;
            fontObject = data;
            //构造字体详细信息面板，currentX和currentY作为点击后面板出现对应的坐标
            clickFont(fontObject, currentX, currentY)
        }
    })
}

//甲骨字详细面板关闭事件
$(".close_info").click(function () {
    $(".detailed_font_info").hide();
})

//构造该字的详细面板信息
function clickFont(currentFontInfo, currentX, currentY) {

    //debugger;
    //甲骨字
    var yuanwen_jgw = String.fromCodePoint(parseInt(currentFontInfo.ZKBM.replace("U", ""), 16));
    //简体
    var jianti_jgw = currentFontInfo.JTZ;
    //繁体
    var jianti_jgw = currentFontInfo.FTZ;
    //诂林
    var gulin_jgw = "";
    //新编
    var xinbian_jgw = "";
    //甲骨片号
    var jgwph = currentFontInfo.JGPH;
    //字编
    var zibian_jgw = "";
    //诂林补
    var glb_jgw = "";
    //類纂
    var lz_jgw = "";
    //相关字形
    var xiangguan_jgw = currentFontInfo.XGZX;

    var child = currentFontInfo.child;
    for (var i = 0; i < child.length; i++) {
        if ("1" == child[i].GLLX) {
            gulin_jgw = child[i].GLZ;
        }
        if ("3" == child[i].GLLX) {
            zibian_jgw = child[i].GLZ;
        }
        if ("4" == child[i].GLLX) {
            xinbian_jgw = child[i].GLZ;
        }
        if ("5" == child[i].GLLX) {
            zibian_jgw = child[i].GLZ;
        }
        if ("6" == child[i].GLLX) {
            glb_jgw = child[i].GLZ;
        }
        if ("7" == child[i].GLLX) {
            lz_jgw = child[i].GLZ;
        }
    }

    //从属
    var congshu_jgw = currentFontInfo.SSZT;

    //简体，用来标识汉典,去除特殊符号
    var jt_jg = ""
    if (jianti_jgw.length >= 1) {
        var regex = new RegExp("[0-9,，.。(暂无)]", "g")
        jianti_jgw = jianti_jgw.replace(regex, "");
        jt_jg = jianti_jgw.substring(0, 1);
    }

    ////字编按钮赋值
    //$(".zibian input").attr("data-id", zibian_jgw);
    //var regex1 = new RegExp("[^0-9，,]", "g");
    //xinbian_jgw = xinbian_jgw.replace(regex1, "");

    //新编显示
    if (xinbian_jgw != "" && xinbian_jgw.indexOf("?") < 0 && xinbian_jgw.indexOf("？") < 0 ) {
        var regex = new RegExp(",，", "g");
        xinbian_jgw = xinbian_jgw.replace(regex, ",");
        $(".xinbian input").removeAttr("disabled");
        $(".xinbian input").attr("data-key", xinbian_jgw);
        $(".xinbian input").css("cursor", "text");
        $(".xinbian input").css("border", "0");
        $(".xinbian .xinbian_content").html("");
        var xinbians = new Array(); //定义一数组

        xinbians = xinbian_jgw.split(","); //字符分割
        var xinbian_html = "";
        for (i = 0; i < xinbians.length; i++) {
            if (xinbians[i] != "") {
                xinbian_html += "<div data-id='" + xinbians[i] + "' title='" + xinbians[i] + " 新编' class='xinbian_id'>[" + xinbians[i] + "]</div>";
            }
        }
        $(".xinbian .xinbian_content").html(xinbian_html);
        $(".xinbian_id").click(function () {
            clickxinbian($(this))
        })
    } else {
        $(".xinbian .xinbian_content").html("");
        $(".xinbian input").attr("disabled", "disabled");
        $(".xinbian input").attr("title", "无");
        $(".xinbian input").attr("data-key", "无");
        $(".xinbian input").css("cursor", "not-allowed");
        $(".xinbian input").css("border", "0");
    }

    //甲骨文显示
    $(".detailed_font_info .jgw_yuanwen input").attr("value", "");
    $(".detailed_font_info .jgw_yuanwen input").attr("value", yuanwen_jgw);
    $(".detailed_font_info .jgw_yuanwen input").attr("disabled", true);
    $(".detailed_font_info .jgw_yuanwen p").attr("title", jianti_jgw);
    $(".detailed_font_info .jgw_yuanwen p").text(jianti_jgw);

    //不存在简体，设置汉典按钮为无法点击  功能已取消
    if (jianti_jgw.length == "" || jianti_jgw == "暂无") {
        $(".handian input").attr("disabled", "disabled")
        $(".handian input").attr("title", "无")
        $(".handian input").attr("data-key", "无")
        $(".handian input").css("cursor", "not-allowed")

        $(".jgwNumber input").attr("disabled", "disabled")
        $(".jgwNumber input").attr("title", "无")
        $(".jgwNumber input").attr("data-key", "无")
        $(".jgwNumber input").css("cursor", "not-allowed")
        $(".jgwNumber a").attr("href", "")

    } else {//存在简体，加入对应汉典信息 和甲骨文
        debugger;
        var rsun = encodeURI (jt_jg);
        rsun = rsun.replace("\\", "%");
        $(".handian input").removeAttr("disabled");
        $(".handian input").attr("title", jianti_jgw + " 汉典");
        $(".handian input").attr("data-key", jt_jg);
        $(".handian input").css("cursor", "pointer");
        $(".handian a").attr("href", "https://www.zdic.net/hans/" + rsun);

        var jgwURL = "http://jgw.aynu.edu.cn/AyjgwSingleSearch?autoLoad=1&id=1&name=BONE&displayDBName=%E8%91%97%E5%BD%95%E5%BA%93&swtosearch=1&fontssw=" + escape(decodeURI(rsun));
        

        $(".jgwNumber a").attr("href", jgwURL);
        $(".jgwNumber a").attr("target", "_blank");
        $(".jgwNumber input").removeAttr("disabled");
        $(".jgwNumber input").attr("title", jianti_jgw + " 检索");
        $(".jgwNumber input").attr("data-key", jt_jg);
        $(".jgwNumber input").css("cursor", "pointer");
    }

    //诂林部分
    if (gulin_jgw != "") {

        var regex = new RegExp("[^0-9]", "g");
        gulin_jgw = gulin_jgw.replace(regex, ",");
        $(".gulin input").removeAttr("disabled");
        $(".gulin input").attr("data-key", gulin_jgw);
        $(".gulin input").css("cursor", "text");
        $(".gulin .gulin_content").html("");
        var gulins = new Array(); //定义一数组

        gulins = gulin_jgw.split(","); //字符分割
        var gulin_html = "";
        for (i = 0; i < gulins.length; i++) {
            if (gulins[i] != "") {
                gulin_html += "<div data-id='" + gulins[i] + "' title='" + gulins[i] + " 诂林' class='gulin_id'>[" + gulins[i] + "]</div>";
            }
        }
        $(".gulin .gulin_content").html(gulin_html);
        $(".gulin_id").click(function () {
            clickgulin($(this));
        })
    } else {
        $(".gulin .gulin_content").html("");
        $(".gulin input").attr("disabled", "disabled");
        $(".gulin input").attr("title", "无");
        $(".gulin input").attr("data-key", "无");
        $(".gulin input").css("cursor", "not-allowed");
        $(".gulin input").css("border", "0");
    }

    //甲骨片号检索
    if (jgwph != "") {
        var regex = new RegExp("[，,]", "g");
        jgwph = jgwph.replace(regex, ",");
        $(".jgph input").removeAttr("disabled");
        $(".jgph input").attr("data-key", gulin_jgw);
        $(".jgph input").css("cursor", "text");
        $(".jgph .jgph_content").html("");
        var jgphs = new Array(); //定义一数组
        jgphs = jgwph.split(","); //字符分割
        var jgph_html = "";
        for (i = 0; i < jgphs.length; i++) {
            if (jgphs[i] != "") {
                jgphs[i] = jgphs[i].replace(regex, "");
                jgph_html += "<div data-id='" + jgphs[i] + "' title='" + jgphs[i] + " 甲骨片号' class='jgph_id jg'>[" + jgphs[i] + "]</div>";
            }
        }
        jgph_html += "<div data-id='" + yuanwen_jgw + "' title='更多' class='jgph_id mo'>[更多]</div>";
        $(".jgph .jgph_content").html(jgph_html);
        $(".mo").click(function () {
			// window.location.href = "./search/index.html?value=" + encodeURI(value) + "&query=" + query + "&key=" + key + "&nav=" + nav + "&type=" + type;
            // window.open(http_url + "/AyjgwSingleSearch/Index?autoLoad=1&id=3&name=BONE&displayDBName=著录库&query=2&strchecklist=1&jgshow=JG&fonts=" + escape(yuanwen_jgw));
            // localStorage.setItem('codeUrl',encodeURIComponent(yuanwen_jgw))
			window.open(http_url + "/home/zl/search/index.html?query=2&key=PM&nav=2&type=0&value=" + encodeURIComponent(yuanwen_jgw));
        })
        $(".jg").click(function () {
            clickjgph($(this));
        })
    } else {
        $(".jgph .jgph_content").html("");
        $(".jgph input").attr("disabled", "disabled");
        $(".jgph input").attr("title", "无");
        $(".jgph input").attr("data-key", "无");
        $(".jgph input").css("cursor", "not-allowed");
        $(".jgph input").css("border", "0");
        var jgph_html = "";
        jgph_html += "<div data-id='" + yuanwen_jgw + "' title='" + yuanwen_jgw + " 甲骨片号' class='jgph_id mo'>[更多]</div>";
        $(".jgph .jgph_content").html(jgph_html);
        $(".mo").click(function () {
			window.open(http_url + "/home/zl/search/index.html?query=2&key=PM&nav=2&type=0&value=" + encodeURIComponent(yuanwen_jgw));
            // window.open(http_url + "/AyjgwSingleSearch/Index?autoLoad=1&id=3&name=BONE&displayDBName=著录库&query=2&jgshow=JG&fonts=" + escape(yuanwen_jgw));
        })
    }
    //字编
    if (zibian_jgw != "") {

        var regex = new RegExp("[^0-9]", "g");
        zibian_jgw = zibian_jgw.replace(regex, ",");
        $(".zibian input").removeAttr("disabled");
        $(".zibian input").attr("data-key", gulin_jgw);
        $(".zibian input").css("cursor", "text");
        $(".zibian .zibian_content").html("");
        var zibians = new Array(); //定义一数组

        zibians = zibian_jgw.split(","); //字符分割
        var zibian_html = "";
        for (i = 0; i < zibians.length; i++) {
            if (zibians[i] != "") {
                zibian_html += "<div data-id='" + zibians[i] + "' title='" + zibians[i] + " 诂林' class='zibian_id'>[" + zibians[i] + "]</div>";
            }
        }
        $(".zibian .zibian_content").html(zibian_html);
        $(".zibian_id").click(function () {
            clickzibian($(this));
        })
    } else {
        $(".zibian .zibian_content").html("");
        $(".zibian input").attr("disabled", "disabled");
        $(".zibian input").attr("title", "无");
        $(".zibian input").attr("data-key", "无");
        $(".zibian input").css("cursor", "not-allowed");
        $(".zibian input").css("border", "0");
    }
    //诂林补
    if (glb_jgw != "") {

        var regex = new RegExp("[^0-9]", "g");
        glb_jgw = glb_jgw.replace(regex, ",");
        $(".gulinb input").removeAttr("disabled");
        $(".gulinb input").attr("data-key", gulin_jgw);
        $(".gulinb input").css("cursor", "text");
        $(".gulinb .gulinb_content").html("");
        var glbs = new Array(); //定义一数组

        glbs = glb_jgw.split(","); //字符分割
        var glb_html = "";
        for (i = 0; i < glbs.length; i++) {
            if (glbs[i] != "") {
                glb_html += "<div data-id='" + glbs[i] + "' title='" + glbs[i] + " 诂林' class='gulinb_id'>[" + glbs[i] + "]</div>";
            }
        }
        $(".gulinb .gulinb_content").html(glb_html);
        $(".gulinb_id").click(function () {
            clickgulinb($(this));
        })
    } else {
        $(".gulinb .gulinb_content").html("");
        $(".gulinb input").attr("disabled", "disabled");
        $(".gulinb input").attr("title", "无");
        $(".gulinb input").attr("data-key", "无");
        $(".gulinb input").css("cursor", "not-allowed");
        $(".gulinb input").css("border", "0");
    }
    //异形体部分
    if (congshu_jgw != "") {
        $(".xiangguanzx_content").html("");
        var regex = new RegExp("[^0-9a-zA-Z]", "g");
        congshu_jgw = congshu_jgw.replace(regex, ",");
        var congshus = new Array();
        congshus = congshu_jgw.split(",");
        var congshu_html = "";
        for (i = 0; i < congshus.length; i++) {
            if (congshus[i] != "") {
                var regex2 = new RegExp("[Uu]", "g");
                var congshu_code = congshus[i].replace(regex2, "");
                if (congshu_code.length == 5) {
                    var cs_z = String.fromCodePoint(parseInt(congshu_code, 16));
                    congshu_html += "<div class='congshu_content_font' data-code='" + congshu_code + "'>" + cs_z + "</div>";
                }
            }
        }
        $(".yixingti_content").html(congshu_html);


    } else {
        $(".yixingti_content").html("<div style='margin-left:10px;'>暂无异形字</div>");
    }

    //類纂
    if (lz_jgw != "") {

        var regex = new RegExp("[^0-9]", "g");
        lz_jgw = lz_jgw.replace(regex, ",");
        $(".lz input").removeAttr("disabled");
        $(".lz input").attr("data-key", gulin_jgw);
        $(".lz input").css("cursor", "text");
        $(".lz .lz_content").html("");
        var lz = new Array(); //定义一数组

        lz = lz_jgw.split(","); //字符分割
        var lz_html = "";
        for (i = 0; i < lz.length; i++) {
            if (lz[i] != "") {
                lz_html += "<div data-id='" + lz[i] + "' title='" + lz[i] + " 類纂' class='lz_id'>[" + lz[i] + "]</div>";
            }
        }
        $(".lz .lz_content").html(lz_html);
        $(".lz_id").click(function () {
            clicklz($(this));
        })
    } else {
        $(".lz .lz_content").html("");
        $(".lz input").attr("disabled", "disabled");
        $(".lz input").attr("title", "无");
        $(".lz input").attr("data-key", "无");
        $(".lz input").css("cursor", "not-allowed");
        $(".lz input").css("border", "0");
    }

    //相关字部分
    if (xiangguan_jgw != "") {
        $(".xiangguanzx_content").html("");
        var regex = new RegExp("[^0-9a-zA-Z]", "g");
        xiangguan_jgw = xiangguan_jgw.replace(regex, ",");
        var xiangguanzxs = new Array();
        xiangguanzxs = xiangguan_jgw.split(",");
        var xiangguan_html = "";
        for (i = 0; i < xiangguanzxs.length; i++) {
            if (xiangguanzxs[i] != "") {
                var regex2 = new RegExp("[Uu]", "g");
                var xiangguan_code = xiangguanzxs[i].replace(regex2, "");
                if (xiangguan_code.length == 5) {
                    var cs_z = String.fromCodePoint(parseInt(xiangguan_code, 16));
                    xiangguan_html += "<div class='xiangguan_content_font' data-code='" + xiangguan_code + "'>" + cs_z + "</div>";
                }
            }
        }
        $(".xiangguanzx_content").html(xiangguan_html);
        $(".xiangguanzx").show();
        //$(".detailed_font_info").css("height", "520px");
        //$(".modalbg").css("height", "520px");

    } else {
        $(".xiangguanzx").hide();
        //$(".detailed_font_info").css("height", "468px");
        //$(".modalbg").css("height", "468px");
    }

    debugger;
    //计算字体信息面板出现的位置
    var docuX = $(window).width() - $(".detailed_font_info").width() - 80;
    var docuY = $(window).height() - $(".detailed_font_info").height() - 80;
    if (docuX < currentX) {
        currentX = currentX - 450;
    }
    if (docuY < currentY) {
        currentY = currentY - 350;
    }

    $(".detailed_font_info").css({
        "display": "block",
        // "left": currentX,
        // "top": currentY,
		"left": '50%',
		"top": '50%',
    })

}

//检索方式选择事件
$(".retrieve_con a").click(function () {
	$('.retrieve').css({"visibility":"visible","margin-bottom":"30px"});
	$("#radical_t").css({ "background": "#ffffff", "color": "#2d9bff" });
	$("#all_font").css({ "background": "#ffffff", "color": "#2d9bff" });
	$("#all_zx").css({ "background": "#ffffff", "color": "#2d9bff" });
	$("#radical_t").parent('a').removeClass("cur");
    $(this).addClass('cur').siblings('a').removeClass("cur");
	$('.jgw_font_content').text("检索结果展示区域！");
    var value = $(this).attr("data-content");
    $("#select-value").val(value);
	$('.retrieve_input').val("");
    if (value == 2) {
        $(".retrieve_input").css("font-family", "jgwfont");
    } else {
        $(".retrieve_input").css("font-family", "inherit");
    }
})

$(".retrieve_condition").change(function () {
    var opt = $(".retrieve_condition").val();
    if (opt == "2") {
        $(".retrieve_input").css("font-family", "jgwfont");
    } else {
        $(".retrieve_input").css("font-family", "inherit");
    }
});

//输入框检索事件
$(".retrieve_btn").click(function () {
    debugger;
    var input = $(".retrieve_input").val();
    if (!input) {
        alert("请输入检索词");
        return;
    }
    //var options = $(".retrieve_condition option:selected");
    //var value = options.val();
	var value = $("#select-value").val();
    var param = value + input;
    var html = "";
    jQuery.getJSON("method/jgwzx.ashx?bm=" + param + "&type=searchzx", function (data, state, xhr) {
        if (state = "success") {
            var zx = data;
            debugger;
            if (zx.length > 0) {
                for (var i = 0; i < zx.length; i++) {
                    var fanti = zx[i].FTZ;
                    var zkbm = zx[i].ZKBM.replace("U", "");

                    var zhuanhuan = String.fromCodePoint(parseInt(zkbm, 16));
                    //正则匹配去除简体中数字以及,，.。
                    if (fanti.length > 1) {
                        var regex = new RegExp("[0-9,，.。(暂无)]", "g")
                        fanti = fanti.replace(regex, "")
                    }
                    html += "<div class='jgw_font_show' title='" + fanti + "' data-fontid='" + zkbm + "'><span class='yuan_jgw'>" + zhuanhuan + "</span><span class='fanti'>" + fanti + "</span></div>";
                }
            } else {
                html += "<span style='float:unset;width:unset'>暂无数据！<span>"
            }
        }
		$("#radical_t").css({ "background": "#ffffff", "color": "#2d9bff" });
		$("#all_font").css({ "background": "#ffffff", "color": "#2d9bff" });
		$("#all_zx").css({ "background": "#ffffff", "color": "#2d9bff" });
        $(".jgw_font_content").html(html);
        $(".pagenav").hide();
		$('.bgc-box').hide();
		$('.jgw_font_content').css( "border-radius", "8px" );
    });

})

$("#selectFile").click(function () {
    $("#file").click();
});
$("#file").change(function () {
    var filename = document.getElementById('file').files[0].name;
    var exten = filename.substring(filename.lastIndexOf(".") + 1);
    if (exten == "xls" || exten == "xlsx" || exten == "ttf") {
        $("#message").text(document.getElementById('file').files[0].name);
		$("#message").attr("title", document.getElementById('file').files[0].name);
        $("#uploadFile").attr("data-content", "1");
    } else {
        $("#message").text("不支持的文件格式！");
        $("#uploadFile").attr("data-content", "2");
    }
});

$("#uploadFile").click(function () {
    uploadFile();
});

function uploadFile() {
    debugger;
    var flag = $("#uploadFile").attr("data-content");
    if (flag == "0") {
        $("#message").text("请选择文件！");
        return;
    } else if (flag == "2") {
        return;
    } else if (flag == "1") {
        var cur = $("#cur-update").val();
        if (cur == "0") {
            //getProcess();
            var file = document.getElementById('file').files[0]; //追加file文件对象
            var formData = new FormData(); //FormData专门用来给ajax向后台传递文件用的
            formData.append("file", file); //向后台传递值、是键值对的形式
            formData.append("action", "upload");
            formData.append("scope", "all");
            $.ajax({
                url: "method/updatezx.ashx",
                datatype: "text",
                type: "post",
                data: formData,
                cache: false, //上传文件无需缓存
                processData: false, //用于对data参数进行序列化处理 这里必须false
                contentType: false,
                success: function (data) {
					alert("上传成功！");
                },
                error: function (data) {
                    alert("上传失败！");
					$("#tips").text("");
                },
            })
        } else if (cur == "1") {
             //getProcess();
            var file = document.getElementById('file').files[0]; //追加file文件对象
            var formData = new FormData(); //FormData专门用来给ajax向后台传递文件用的
            formData.append("file", file); //向后台传递值、是键值对的形式
            $.ajax({
                url: "method/updatezk.ashx",
                datatype: "text",
                type: "post",
                data: formData,
                cache: false, //上传文件无需缓存
                processData: false, //用于对data参数进行序列化处理 这里必须false
                contentType: false,
                success: function (data) {
					alert("上传成功！");
                },
                error: function (data) {
                    alert("上传失败！");
					$("#tips").text("");
                },
            })
        } else if (cur == "2") {
             //getProcess();
            var file = document.getElementById('file').files[0]; //追加file文件对象
            var formData = new FormData(); //FormData专门用来给ajax向后台传递文件用的
            formData.append("file", file); //向后台传递值、是键值对的形式
            formData.append("action", "upload");
            formData.append("scope", "part");
            $.ajax({
                url: "method/updatezx.ashx",
                datatype: "text",
                type: "post",
                data: formData,
                cache: false, //上传文件无需缓存
                processData: false, //用于对data参数进行序列化处理 这里必须false
                contentType: false,
                success: function (data) {
					alert("上传成功！");
                },
                error: function (data) {
                    alert("上传失败！");
					$("#tips").text("");
                },
            })
        }
    }
}

function getProcess() {
	$.ajax({
		url: "method/getupdatevalue.ashx?",
		type: 'get',
		dataType: "text",
		success: function (data) {
			$(".progress").css("display", "block");
			$(".progress-bar").css("width", data);
			if (data == "100.00%") {
				$("#tips").text("上传完成");
			} else {
				getProcess2()
			}
		},
		error: function (XMLHttpRequest, textStatus, errorThrown) {
			$("#tips").text("");
		}
	})
}

function getProcess2() {
    //2秒请求一次进度条的数据
    timer = setInterval(function () {
        $.ajax({
            url: "method/getupdatevalue.ashx?",
            type: 'get',
            dataType: "text",
            success: function (data) {
				$(".progress").css("display", "block");
                $(".progress-bar").css("width", data);
                if (data == "100.00%") {
                    $("#tips").text("上传完成");
                    clearInterval(timer);
                } else {
                    $("#tips").text("正在上传，请稍等...");
                }
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
				$("#tips").text("");
				clearInterval(timer);
            }
        })
    }, 2000);
}

function getProcessZk() {
    debugger;
    var data = 0;
    timer = setInterval(function () {
        data = data + 5;
        $(".progress-bar").css("width", data + ".00%");

        if (data == 100) {
            clearInterval(timer);
        }
    }, 1000);
}

$("#update a").click(function () {
	$(this).addClass('other-cur').siblings('a').removeClass("other-cur");
})
$("#alertFrom").click(function () {
    $("#cur-update").val("0");
	$("#uploadFile").attr("data-content", "0");
	$("#message").text("请选择文件！");
	$("#tips").text("");
	$(".progress").css("display", "none");
	$(".progress-bar").css("width", "0.00%");
    $(".uploadbox").show();
});

$("#alertFrom-zt").click(function () {
    $("#cur-update").val("1");
	$("#uploadFile").attr("data-content", "0");
	$("#message").text("请选择文件！");
	$("#tips").text("");
	$(".progress").css("display", "none");
	$(".progress-bar").css("width", "0.00%");
    $(".uploadbox").show();
});

$("#alertFrom-pa").click(function () {
    $("#cur-update").val("2");
	$("#uploadFile").attr("data-content", "0");
	$("#message").text("请选择文件！");
	$("#tips").text("");
	$(".progress").css("display", "none");
	$(".progress-bar").css("width", "0.00%");
    $(".uploadbox").show();
});

$(".upload_close").click(function () {
    debugger;
	$("#update a").removeClass("other-cur");
    $(".progress-bar").css("width", "0.00%");
    $(".uploadbox").hide();
});

//面板拖拽事件，字体信息面板、部首表面板、手写输入法面板
var dragging = false;
var iX, iY;
var pageWidth = $(window).width();
var pageHeight = $(window).height();
var handle = null;
// $(".drag_dom").mousedown(function (e) {
//     var _this = $(this);
//     handle = setTimeout(function () {
//         var positionDiv = _this.offset();
//         var divX = positionDiv.left;
//         var divY = positionDiv.top;
//         var distenceX1 = e.pageX;
//         var distenceY1 = e.pageY;
//         $(document).mousemove(function (e1) {
//             var distenceX2 = e1.pageX;
//             var distenceY2 = e1.pageY;
//             var x = distenceX1 - distenceX2;
//             var y = distenceY1 - distenceY2;
//             distenceX1 = distenceX2;
//             distenceY1 = distenceY2;
//             var exceptWidth = divX - x;
//             var exceptHeight = divY - y;

//             if (exceptHeight > pageHeight) {
//                 exceptHeight = pageHeight;
//             }
//             if (exceptWidth > pageWidth) {
//                 exceptWidth = pageWidth;
//             }
//             if (exceptHeight < -80) {
//                 exceptHeight = -80;
//             }
//             if (exceptWidth < -20) {
//                 exceptWidth = -20;
//             }
//             divX = exceptWidth;
//             divY = exceptHeight;
//             _this.css({
//                 'left': exceptWidth + 'px',
//                 'top': exceptHeight + 'px',
// 				'transform':'none'
//             });
//         })
//         $(document).mouseup(function () {
//             $(document).off('mousemove');
//             clearTimeout(handle);
//         })
//     }, 50);
// })

$(".retrieve_input").keydown(function (e) {//当按下按键时
    if (e.which == 13) {//.which属性判断按下的是哪个键，回车键的键位序号为13
        // $('button.search123').trigger("click");//触发搜索按钮的点击事件
        $(".retrieve_btn").click();
    }
});

//诂林功能
function clickgulin(e) {
    var search_key = e.attr("data-id")
    window.open("child/gl.html?url=" + search_key);
}

//新编功能
function clickxinbian(e) {
    var search_key = e.attr("data-id")
    window.open("child/xb.html?url=" + search_key);
}
//字编
function clickzibian(e) {
    var search_key = e.attr("data-id")
    window.open("child/zb.html?url=" + search_key);
}
//诂林补
function clickgulinb(e) {
    var search_key = e.attr("data-id")
    window.open("child/glb.html?url=" + search_key);
}
//類纂
function clicklz(e) {
    var search_key = e.attr("data-id")
    window.open("child/lz.html?url=" + search_key);
}
//甲骨片号功能
function clickjgph(e) {
    var search_key = e.attr("data-id")
    $.ajax({
        url: "method/jgwzx.ashx?type=bonesysid&bm=" + search_key,
        type: "get",
        dataType:"text",
        success: function (result) {
            if (result == 0) {
                alert("著录库暂无此片号！")
            } else {
                window.open("/home/zl/detail/index.html?id=" + result);
            }
        }
    })
}

$("#daochu").click(function () {
 
    window.location.href = "/AynuFont/ExportToExcel";
})

$("#zhuxiao").click(function (){
    $.getJSON("method/LoginOut.ashx", function (data, status, xhr) {
        if (data != "") {
            if (data == "ok") {
                $("#denglu").text("登录");
                $("#zhuxiao").hide();
                $("#denglu").attr("href", "/home/account/index.html?type=login&returnUrl=" + encodeURIComponent("/home/zx/index.html"));
            } else {
                alert("业务出错！")
            }
        }
    })


})