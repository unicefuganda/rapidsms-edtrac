function smc_meetings(schools, meetings) {
    var schools;
    var meetings;
    meeting_chart = new Highcharts.Chart({
        chart: {
            renderTo: 'smc_meetings',
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false
        },
        title: {
            text: 'SMC Meetings this School Term'
        },
        tooltip: {
            formatter: function() {
                return '<b>'+ this.point.name +'</b>: '+ this.percentage +' %';
            }
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true
                },
                showInLegend: false
            }
        },
        series: [{
            type: 'pie',
            name: 'Browser share',
            data: [
                ['one meeting',  78],
                ['two meetings',       9],
                ['Three meetings', 13]
            ],
        }]
    });
}


function violence_cases(xVals, yVals, title){
    var x_vals = xVals.split("','");
    var b = yVals.split(",");
    var violence = [];
    for(i=0; i<b.length; i++){
        violence.push(parseFloat(b[i]));
    }
    var violence_chart;
    violence_chart = new Highcharts.Chart(
        {
            chart: {
                renderTo:'violence',
                defaultSeriesType:'column',
                margin:[50,50,100,80]
            },
            title :{
                text : title
            },
            xAxis:{
                categories : x_vals

            },
            labels : {
                rotation : -45,
                align : 'right',
                style : {
                    font:'normal 13px Verdana, sans-serif'
                }
            },
            yAxis:{
                min: 0,
                title : {
                    text : 'Number of Cases'
                }
            },
            legend:{
                enabled:false
            },
            tooltip:{
                formatter:function(){
                    return '<b>'+ this.x+'</b><br/>'+ 'Violence cases: '+Highcharts.numberFormat(this.y, 1) + ' cases';
                }
            },
            series:[
                {
                    name: 'Numbers',
                    data : violence,
                    dataLabels:{
                        enabled:true,
                        rotation:-90,
                        color:'#FFFFFF',
                        align:'right',
                        x:-3,
                        y:10,
                        formatter:function(){
                            return this.y;
                        },
                        style:{
                            font:'normal 13px Verdana, sans-serif'
                        }
                    }
                }
            ]
        }
    );
}


//pie chart
function pie(data, chart_title, series_title, selector_id, tooltip_text) {

    var d = data.split(",");
    var data_array = [];
    for(i=0;i<d.length; i++){
        x = d[i].split('-');
        data_array.push([x[0], parseInt(x[1])]);
    }
    var chart;
    chart = new Highcharts.Chart({
        chart: {
            //renderTo: 'lunch',
            renderTo: selector_id,
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false
        },
        title: {
            text: chart_title
        },
        tooltip: {
            formatter: function() {
                //return this.percentage +' % \n didn\'t have meals';
                return this.percentage + ' %' + tooltip_text;
            }
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true
                },
                showInLegend:false
            }
        },
        series: [{
            type: 'pie',
            //name: 'Lunch at School',
            name: series_title,
            data: lunch_data

        }]
    });
}

function load_progress_chart(val1, val2){
    var val1, val2;
    if (val1 > 100 || val2 > 100){
        // pervasive checking...
        alert("Progress chart can't load for values greater than 100 denied");
    }
    else{
        $("#progress_p3").progressbar({value: val1});
        $("#progress_p6").progressbar({value:val2});
        $("#progress_p3 > div").append(val1 + '%').addClass('pretify');
        $("#progress_p6 > div").append(val2 + '%').addClass('pretify');
    }
}