var width = 360;
var height = 180;

nv.addGraph(function() {
    var chart = nv.models.pie()
            .x(function(d) { return d.key; })
            .y(function(d) { return d.y; })
            .width(width)
            .height(height)
            ;

    d3.select("#svg_chart")
            .datum(chart_data)
            .transition().duration(1200)
            .attr("width", width)
            .attr("height", height)
            .attr('viewBox','0 0 '+(Math.min(width,height)+10)+' '+(Math.min(width,height)+10))
            .attr('preserveAspectRatio','xMinYMin')
            .call(chart);

    // LISTEN TO CLICK EVENTS ON THE SLICES OF THE PIE
    // chart.dispatch.on('elementClick', function() {
    //   code...
    // });

    // OTHER EVENTS DISPATCHED BY THE PIE INCLUDE: elementDblClick, elementMouseover, elementMouseout, elementMousemove, renderEnd
    // @see nv.models.pie
    return chart;
});
