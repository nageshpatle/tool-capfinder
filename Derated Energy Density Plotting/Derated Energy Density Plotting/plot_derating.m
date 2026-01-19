%% Plotting Class II Derated Energy Density
close all;
clear all;

% data = readmatrix("Ceramic_20211111.csv",'Range',[2,1]);
data = readtable("MLCC_TDK_20210513.csv");
% data = data(1:2552,:);

figure(1);
hold on;

for i = 1:2551

    C_Cv = str2num(cell2mat(table2array(data(i,8))));
    V_Cv = str2num(cell2mat(table2array(data(i,9))));
    volume = table2array(data(i,6));
    density = (1/2)*C_Cv.*V_Cv.^2./volume;
    technology = data(i,3);
    partnum = data(i,2);

    p = plot(V_Cv,density);

    disp(i);
    datatip(p,'Visible','off'); % Hide initial datatip
    p.DataTipTemplate.DataTipRows(1).Label = 'Voltage';
    p.DataTipTemplate.DataTipRows(2).Label = 'Energy Density';
    p.DataTipTemplate.DataTipRows(end+1) = dataTipTextRow("PartNumber",repmat(string(partnum.MfrPartName{1}),1,length(V_Cv)));

    xlabel('Voltage [V]');
    ylabel({'Class II Derated','Energy Density [J/mm^3]'});

end

% Configure data tips
% datatip(plot_object_ii,'Visible','off'); % Hide initial datatip
% plot_object_ii.DataTipTemplate.DataTipRows(1).Label = xAxis_label;
% plot_object_ii.DataTipTemplate.DataTipRows(2).Label = yAxis_label;
% if N_axes == 3
%     plot_object_ii.DataTipTemplate.DataTipRows(3).Label = zAxis_label;
% end
% plot_object_ii.DataTipTemplate.DataTipRows(end+1) = dataTipTextRow("Type", repmat({structPlot_axisSelect.legend.name{ii}},length(structPlot_axisSelect.data.mfr{ii}),1));
% plot_object_ii.DataTipTemplate.DataTipRows(end+1) = dataTipTextRow("Mfr", structPlot_axisSelect.data.mfr{ii});
% plot_object_ii.DataTipTemplate.DataTipRows(end+1) = dataTipTextRow("MPN", structPlot_axisSelect.data.mpn{ii});


% set(gca, 'XScale', 'log');
% set(gca, 'YScale', 'log');

hold off;

set_figure_style(2);