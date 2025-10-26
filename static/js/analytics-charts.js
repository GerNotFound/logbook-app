
(function (window) {
  'use strict';

  function deepClonePoint(point) {
    if (!point) {
      return null;
    }
    return {
      x: point.x,
      y: point.y,
      value: point.value,
      raw: point.raw,
      label: point.label,
      unit: point.unit,
    };
  }

  function createSnapshot(state) {
    return {
      labels: state.labels.slice(),
      datasets: state.renderedDatasets.map(function (dataset) {
        return {
          label: dataset.label,
          color: dataset.color,
          unit: dataset.unit,
          data: dataset.data.slice(),
          raw: dataset.raw ? dataset.raw.slice() : null,
          points: dataset.points.map(deepClonePoint),
        };
      }),
    };
  }

  function assign(target, source) {
    for (var key in source) {
      if (Object.prototype.hasOwnProperty.call(source, key)) {
        target[key] = source[key];
      }
    }
    return target;
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function prepareCanvas(state) {
    var canvas = state.canvas;
    var width = canvas.clientWidth;
    var height = canvas.clientHeight;
    if (!width || !height) {
      return null;
    }

    var dpr = window.devicePixelRatio || 1;
    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    var ctx = state.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    return { width: width, height: height };
  }

  function defaultYFormatter(value) {
    return Math.round(value).toString();
  }

  function defaultTooltipFormatter(dataset, point) {
    if (point.raw == null) {
      return '—';
    }
    var value = point.raw;
    if (dataset.unit) {
      value += ' ' + dataset.unit;
    }
    return value;
  }

  function AnalyticsChartsModule() {
    var resizeObserverSupported = typeof ResizeObserver !== 'undefined';

    function renderLineChart(canvas, config) {
      if (!canvas) {
        throw new Error('Canvas element richiesto per il grafico.');
      }

      var ctx = canvas.getContext('2d');
      var state = {
        canvas: canvas,
        ctx: ctx,
        labels: Array.isArray(config.labels) ? config.labels.slice() : [],
        datasetsConfig: Array.isArray(config.datasets) ? config.datasets.slice() : [],
        renderedDatasets: [],
        padding: assign({ top: 24, right: 28, bottom: 48, left: 64 }, config.padding || {}),
        yRange: config.yRange || null,
        yTicks: typeof config.yTicks === 'number' ? config.yTicks : 5,
        yFormatter: typeof config.yFormatter === 'function' ? config.yFormatter : defaultYFormatter,
        tooltipFormatter: config.tooltip && typeof config.tooltip.valueFormatter === 'function'
          ? config.tooltip.valueFormatter
          : defaultTooltipFormatter,
        subscribers: [],
        xPositions: [],
        highlightIndex: null,
        rafHandle: null,
        snapshot: null,
      };

      function notify() {
        if (!state.snapshot) {
          return;
        }
        state.subscribers.forEach(function (cb) {
          cb(state.snapshot);
        });
      }

      function computeYRange() {
        if (state.yRange && typeof state.yRange.min === 'number' && typeof state.yRange.max === 'number') {
          return {
            min: state.yRange.min,
            max: state.yRange.max,
          };
        }

        var minValue = Number.POSITIVE_INFINITY;
        var maxValue = Number.NEGATIVE_INFINITY;
        state.datasetsConfig.forEach(function (dataset) {
          (dataset.data || []).forEach(function (value) {
            if (value == null || !isFinite(value)) {
              return;
            }
            if (value < minValue) {
              minValue = value;
            }
            if (value > maxValue) {
              maxValue = value;
            }
          });
        });

        if (minValue === Number.POSITIVE_INFINITY || maxValue === Number.NEGATIVE_INFINITY) {
          minValue = 0;
          maxValue = 1;
        }
        if (minValue === maxValue) {
          var offset = Math.abs(minValue) * 0.1 || 1;
          minValue -= offset;
          maxValue += offset;
        }
        return { min: minValue, max: maxValue };
      }

      function scheduleDraw() {
        if (state.rafHandle) {
          return;
        }
        state.rafHandle = window.requestAnimationFrame(function () {
          state.rafHandle = null;
          draw();
        });
      }

      function draw() {
        var metrics = prepareCanvas(state);
        if (!metrics) {
          return;
        }

        var width = metrics.width;
        var height = metrics.height;
        var padding = state.padding;
        var plotWidth = Math.max(1, width - padding.left - padding.right);
        var plotHeight = Math.max(1, height - padding.top - padding.bottom);
        var yRange = computeYRange();
        var yMin = yRange.min;
        var yMax = yRange.max;
        var ctx = state.ctx;

        ctx.save();
        ctx.fillStyle = 'rgba(255, 255, 255, 0.02)';
        ctx.fillRect(padding.left, padding.top, plotWidth, plotHeight);
        ctx.restore();

        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, height - padding.bottom);
        ctx.lineTo(width - padding.right, height - padding.bottom);
        ctx.stroke();
        ctx.restore();

        var yTicks = Math.max(2, state.yTicks);
        for (var i = 0; i <= yTicks; i++) {
          var ratio = i / yTicks;
          var y = padding.top + plotHeight - ratio * plotHeight;
          ctx.save();
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(padding.left, y);
          ctx.lineTo(width - padding.right, y);
          ctx.stroke();
          ctx.restore();

          var tickValue = yMin + (yMax - yMin) * ratio;
          var label = state.yFormatter(tickValue);
          ctx.save();
          ctx.fillStyle = 'rgba(235, 236, 240, 0.8)';
          ctx.font = '12px "Segoe UI", Roboto, sans-serif';
          ctx.textAlign = 'right';
          ctx.textBaseline = 'middle';
          ctx.fillText(label, padding.left - 10, y);
          ctx.restore();
        }

        var labels = state.labels;
        var labelCount = labels.length;
        state.xPositions = new Array(labelCount);
        if (labelCount === 1) {
          state.xPositions[0] = padding.left + plotWidth / 2;
        } else {
          for (var idx = 0; idx < labelCount; idx++) {
            state.xPositions[idx] = padding.left + (plotWidth * idx) / (labelCount - 1);
          }
        }

        var maxXTicks = Math.min(8, labelCount);
        var step = labelCount > maxXTicks ? Math.ceil(labelCount / maxXTicks) : 1;
        var usedIndices = {};
        ctx.save();
        ctx.fillStyle = 'rgba(235, 236, 240, 0.85)';
        ctx.font = '12px "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        for (var li = 0; li < labelCount; li += step) {
          usedIndices[li] = true;
        }
        usedIndices[labelCount - 1] = true;
        usedIndices[0] = true;
        for (var key in usedIndices) {
          if (!Object.prototype.hasOwnProperty.call(usedIndices, key)) {
            continue;
          }
          var index = parseInt(key, 10);
          var label = labels[index];
          var x = state.xPositions[index];
          ctx.fillText(label, x, height - padding.bottom + 10);
        }
        ctx.restore();

        function mapY(value) {
          if (value == null || !isFinite(value)) {
            return null;
          }
          var ratio;
          if (yMax === yMin) {
            ratio = 0.5;
          } else {
            ratio = (value - yMin) / (yMax - yMin);
          }
          ratio = clamp(ratio, 0, 1);
          return padding.top + (1 - ratio) * plotHeight;
        }

        state.renderedDatasets = state.datasetsConfig.map(function (datasetConfig) {
          var dataset = {
            label: datasetConfig.label || 'Serie',
            color: datasetConfig.color || '#0d6efd',
            unit: datasetConfig.unit || '',
            lineWidth: datasetConfig.lineWidth || 2,
            pointRadius: datasetConfig.pointRadius || 3,
            data: [],
            raw: datasetConfig.raw ? datasetConfig.raw.slice() : null,
            points: new Array(labelCount),
          };

          var dataValues = Array.isArray(datasetConfig.data) ? datasetConfig.data : [];
          var hasValue = false;
          for (var di = 0; di < labelCount; di++) {
            var value = dataValues[di];
            var numericValue = value == null || !isFinite(value) ? null : Number(value);
            dataset.data.push(numericValue);
            if (numericValue != null) {
              hasValue = true;
            }
          }

          ctx.save();
          ctx.strokeStyle = dataset.color;
          ctx.lineWidth = dataset.lineWidth;
          ctx.lineJoin = 'round';
          ctx.lineCap = 'round';
          ctx.beginPath();
          var drawing = false;
          for (var pi = 0; pi < labelCount; pi++) {
            var pointValue = dataset.data[pi];
            var x = state.xPositions[pi];
            var yCoord = mapY(pointValue);
            if (pointValue == null || yCoord == null) {
              drawing = false;
              dataset.points[pi] = null;
              continue;
            }
            dataset.points[pi] = {
              x: x,
              y: yCoord,
              value: pointValue,
              raw: dataset.raw && dataset.raw.length > pi ? dataset.raw[pi] : pointValue,
              label: labels[pi],
              unit: dataset.unit,
            };
            if (!drawing) {
              ctx.moveTo(x, yCoord);
              drawing = true;
            } else {
              ctx.lineTo(x, yCoord);
            }
          }
          ctx.stroke();
          ctx.restore();

          if (hasValue) {
            ctx.save();
            ctx.fillStyle = dataset.color;
            for (var pt = 0; pt < labelCount; pt++) {
              var point = dataset.points[pt];
              if (!point) {
                continue;
              }
              ctx.beginPath();
              ctx.arc(point.x, point.y, dataset.pointRadius, 0, Math.PI * 2);
              ctx.fill();
            }
            ctx.restore();
          }

          return dataset;
        });

        if (state.highlightIndex != null && state.xPositions[state.highlightIndex] != null) {
          var highlightX = state.xPositions[state.highlightIndex];
          ctx.save();
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(highlightX, padding.top);
          ctx.lineTo(highlightX, height - padding.bottom);
          ctx.stroke();
          ctx.restore();

          state.renderedDatasets.forEach(function (dataset) {
            var highlightPoint = dataset.points[state.highlightIndex];
            if (!highlightPoint) {
              return;
            }
            ctx.save();
            ctx.fillStyle = '#000';
            ctx.beginPath();
            ctx.arc(highlightPoint.x, highlightPoint.y, dataset.pointRadius + 3, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = dataset.color;
            ctx.beginPath();
            ctx.arc(highlightPoint.x, highlightPoint.y, dataset.pointRadius + 1.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
          });
        }

        state.snapshot = createSnapshot(state);
        notify();
      }

      function subscribe(callback) {
        if (typeof callback !== 'function') {
          return function () {};
        }
        state.subscribers.push(callback);
        if (state.snapshot) {
          callback(state.snapshot);
        }
        return function () {
          var index = state.subscribers.indexOf(callback);
          if (index !== -1) {
            state.subscribers.splice(index, 1);
          }
        };
      }

      function handlePointerMove(event) {
        if (!state.snapshot || !state.snapshot.labels.length) {
          return;
        }
        var rect = state.canvas.getBoundingClientRect();
        var offsetX = event.clientX - rect.left;
        var offsetY = event.clientY - rect.top;
        var nearestIndex = null;
        var smallestDistance = Infinity;
        for (var i = 0; i < state.xPositions.length; i++) {
          var xPos = state.xPositions[i];
          if (xPos == null) {
            continue;
          }
          var distance = Math.abs(xPos - offsetX);
          if (distance < smallestDistance) {
            smallestDistance = distance;
            nearestIndex = i;
          }
        }
        if (nearestIndex == null) {
          hideTooltip();
          return;
        }

        var rows = [];
        state.renderedDatasets.forEach(function (dataset) {
          var point = dataset.points[nearestIndex];
          if (!point) {
            return;
          }
          rows.push({ dataset: dataset, point: point });
        });
        if (!rows.length) {
          hideTooltip();
          return;
        }

        if (state.highlightIndex !== nearestIndex) {
          state.highlightIndex = nearestIndex;
          scheduleDraw();
        }

        showTooltip(offsetX, offsetY, state.snapshot.labels[nearestIndex], rows);
      }

      function handlePointerLeave() {
        state.highlightIndex = null;
        scheduleDraw();
        hideTooltip();
      }

      var tooltipEl = document.createElement('div');
      tooltipEl.className = 'chart-tooltip';
      state.canvas.parentElement.appendChild(tooltipEl);

      function showTooltip(x, y, heading, rows) {
        if (!rows.length) {
          hideTooltip();
          return;
        }
        var content = '<div class="chart-tooltip-heading">' + heading + '</div>';
        rows.forEach(function (row) {
          var formatter = state.tooltipFormatter || defaultTooltipFormatter;
          var value = formatter(row.dataset, row.point);
          content += '<div class="chart-tooltip-row">' +
            '<span class="chart-tooltip-label"><span class="chart-tooltip-dot" style="background:' + row.dataset.color + '"></span>' + row.dataset.label + '</span>' +
            '<span class="chart-tooltip-value">' + value + '</span>' +
            '</div>';
        });
        tooltipEl.innerHTML = content;
        tooltipEl.style.left = x + 'px';
        tooltipEl.style.top = y + 'px';
        tooltipEl.classList.add('visible');
      }

      function hideTooltip() {
        tooltipEl.classList.remove('visible');
      }

      function destroy() {
        if (resizeObserver) {
          resizeObserver.disconnect();
        } else {
          window.removeEventListener('resize', scheduleDraw);
        }
        state.canvas.removeEventListener('mousemove', handlePointerMove);
        state.canvas.removeEventListener('mouseleave', handlePointerLeave);
        tooltipEl.remove();
      }

      var resizeObserver;
      if (resizeObserverSupported) {
        resizeObserver = new ResizeObserver(function () {
          scheduleDraw();
        });
        resizeObserver.observe(canvas);
      } else {
        window.addEventListener('resize', scheduleDraw);
      }

      state.canvas.addEventListener('mousemove', handlePointerMove);
      state.canvas.addEventListener('mouseleave', handlePointerLeave);

      scheduleDraw();

      return {
        subscribe: subscribe,
        redraw: scheduleDraw,
        destroy: destroy,
        setTooltipFormatter: function (formatter) {
          if (typeof formatter === 'function') {
            state.tooltipFormatter = formatter;
            scheduleDraw();
          }
        },
      };
    }

    function renderLegend(container, datasets) {
      if (!container) {
        return;
      }
      container.innerHTML = '';
      datasets.forEach(function (dataset) {
        var item = document.createElement('span');
        item.className = 'chart-legend-item';
        item.innerHTML = '<span class="chart-legend-swatch" style="background:' + dataset.color + '"></span>' +
          '<span>' + dataset.label + '</span>';
        container.appendChild(item);
      });
    }

    return {
      renderLineChart: renderLineChart,
      renderLegend: renderLegend,
    };
  }

  window.AnalyticsCharts = AnalyticsChartsModule();
  try {
    window.dispatchEvent(new CustomEvent('analyticsChartsReady'));
  } catch (err) {
    window.dispatchEvent(new Event('analyticsChartsReady'));
  }
})(window);
