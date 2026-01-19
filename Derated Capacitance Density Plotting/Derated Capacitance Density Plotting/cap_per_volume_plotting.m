%% Capacitance Per Volume Plotting
% author: Nathan Biesterfeld
close all;
clear all;

%% Capacitor Volumes
volume0805 = 2*1.25*1.25; % [mm^3]
volume0603 = 1.6*0.8*0.8;
volume0402 = 1*0.5*0.5;   
volume0201 = 0.6*0.3*0.3;

%% 50V Capacitors
% C2012X5R1H106K125AC
V_Cv = [0,4,6.3,10,16,25,35,50];
C_Cv = [10,8.588,7.069,4.949,2.857,1.577,1.038,0.704];
rhoC = C_Cv/volume0805;
C2012X5R1H106K125AC = struct('Part_Number','C2012X5R1H106K125AC','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R61H105ME05
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R61H105ME05_50V_0402.csv','0402',1);
GRM155R61H105ME05 = struct('Part_Number','GRM155R61H105ME05','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM21BR61H106ME43
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM21BR61H106ME43_50V_0805.csv','0805',10);
GRM21BR61H106ME43 = struct('Part_Number','GRM21BR61H106ME43','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% MSASU168BB5225KTNA01
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('MSASU168BB5225KTNA01_50V_0603.csv','0603',2.2);
MSASU168BB5225KTNA01 = struct('Part_Number','MSASU168BB5225KTNA01','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R61H474ME11
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R61H474ME11_50V_0402.csv','0402',0.47);
GRM155R61H474ME11 = struct('Part_Number','GRM155R61H474ME11','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% MSASU105AB5474KFNA01
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('MSASU105AB5474KFNA01_50V_0402.csv','0402',0.47);
MSASU105AB5474KFNA01 = struct('Part_Number','MSASU105AB5474KFNA01','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

%% 35V Capacitors
% C1005X5R1V225M050BC
V_Cv = [0,1.25,2,2.5,3.15,4,5,6.3,8,10,12.5,16,25,35];
C_Cv = [2.2,1.783,1.385,1.147,0.930,0.702,0.540,0.410,0.304,0.229,0.175,0.134,0.089,0.066];
rhoC = C_Cv/volume0402;
C1005X5R1V225M050BC = struct('Part_Number','C1005X5R1V225M050BC','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM188R6YA106MA73
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM188R6YA106MA73_35V_0603.csv','0603',10);
GRM188R6YA106MA73 = struct('Part_Number','GRM188R6YA106MA73','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% C2012X5R1V226M125AC
V_Cv = [0,1.25,2,2.5,3.15,4,5,6.3,8,10,12.5,16,25,35];
C_Cv = [22,20.711,17.956,15.900,13.716,11.052,8.882,7.012,5.354,4.075,3.101,2.325,1.462,1.044];
rhoC = C_Cv/volume0805;
C2012X5R1V226M125AC = struct('Part_Number','C2012X5R1V226M125AC','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R6YA225ME11
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R6YA225ME11_35V_0402.csv','0402',2.2);
GRM155R6YA225ME11 = struct('Part_Number','GRM155R6YA225ME11','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% C2012X5R1V106M085AC
V_Cv = [0,1.25,2,2.5,3.15,4,5,6.3,8,10,12.5,16,25,35];
C_Cv = [10,9.233,8.178,7.36,6.435,5.277,4.27,3.319,2.49,1.876,1.414,1.044,0.637,0.457];
rhoC = C_Cv/volume0805;
C2012X5R1V106M085AC = struct('Part_Number','C2012X5R1V106M085AC','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM188R6YA475ME15
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM188R6YA475ME15_35V_0603.csv','0603',4.7);
GRM188R6YA475ME15 = struct('Part_Number','GRM188R6YA475ME15','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R6YA105ME11
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R6YA105ME11_35V_0402.csv','0402',1);
GRM155R6YA105ME11 = struct('Part_Number','GRM155R6YA105ME11','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

%% 25V Capacitors
% GRM188C61E226ME01
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM188C61E226ME01_25V_0603.csv','0603',22);
GRM188C61E226ME01 = struct('Part_Number','GRM188C61E226ME01','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM188R61E106MA73
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM188R61E106MA73_25V_0603.csv','0603',10);
GRM188R61E106MA73 = struct('Part_Number','GRM188R61E106MA73','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R61E225ME15
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R61E225ME15_25V_0402.csv','0402',2.2);
GRM155R61E225ME15 = struct('Part_Number','GRM155R61E225ME15','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% ZRB18AR61E106ME01
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('ZRB18AR61E106ME01_25V_0603.csv','0603',10);
ZRB18AR61E106ME01 = struct('Part_Number','ZRB18AR61E106ME01','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM188R61E106KA73
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM188R61E106KA73_25V_0603.csv','0603',10);
GRM188R61E106KA73 = struct('Part_Number','GRM188R61E106KA73','Package','0603','Volume',volume0603,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM21BR61E226ME44
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM21BR61E226ME44_25V_0805.csv','0805',22);
GRM21BR61E226ME44 = struct('Part_Number','GRM21BR61E226ME44','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

%% 16V Capacitors
% GRM155R61C225KE11
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R61C225KE11_16V_0402.csv','0402',2.2);
GRM155R61C225KE11 = struct('Part_Number','GRM155R61C225KE11','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM219R61C226ME15
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM219R61C226ME15_16V_0805.csv','0805',22);
GRM219R61C226ME15 = struct('Part_Number','GRM219R61C226ME15','Package','0805','Volume',volume0805,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

%% 10V Capacitors
% GRM158R61A226ME15
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM158R61A226ME15_10V_0402.csv','0402',22);
GRM158R61A226ME15 = struct('Part_Number','GRM158R61A226ME15','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM033R61A225ME47
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM033R61A225ME47_10V_0201.csv','0201',2.2);
GRM033R61A225ME47 = struct('Part_Number','GRM033R61A225ME47','Package','0201','Volume',volume0201,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

% GRM155R61A106ME11
[V_Cv,C_Cv,rhoC] = getMurataDeratingCurve('GRM155R61A106ME11_10V_0402.csv','0402',10);
GRM155R61A106ME11 = struct('Part_Number','GRM155R61A106ME11','Package','0402','Volume',volume0402,'V_Cv',V_Cv,'C_Cv',C_Cv,'rho_C',rhoC);

%% Capacitance Per Volume Plotting
capacitors = [C2012X5R1H106K125AC,GRM155R61H105ME05,GRM21BR61H106ME43,MSASU168BB5225KTNA01,GRM155R61H474ME11,MSASU105AB5474KFNA01, ...
              C1005X5R1V225M050BC,GRM188R6YA106MA73,C2012X5R1V226M125AC,GRM155R6YA225ME11,C2012X5R1V106M085AC,GRM188R6YA475ME15,GRM155R6YA105ME11, ...
              GRM188C61E226ME01,GRM188R61E106MA73,GRM155R61E225ME15,ZRB18AR61E106ME01,GRM188R61E106KA73,GRM21BR61E226ME44, ...
              GRM155R61C225KE11,GRM219R61C226ME15, ...
              GRM158R61A226ME15,GRM033R61A225ME47,GRM155R61A106ME11];

colors = ["#C82423","#2878B5","#7E2F8E","#3C8F40"]; % red, blue, purple, green


fig = figure(1);
plt = semilogy(C2012X5R1H106K125AC.V_Cv,C2012X5R1H106K125AC.C_Cv/volume0805,'color',colors(1));
plt.DataTipTemplate.DataTipRows(1).Label = 'Voltage';
plt.DataTipTemplate.DataTipRows(2).Label = 'Derated Capacitance Per Unit Volume [uF/mm^3]';
plt.DataTipTemplate.DataTipRows(3).Label = 'Part: C2012X5R1H106K125AC';
plt.DataTipTemplate.DataTipRows(4).Label = 'Package: 0805';

hold on;
for i = 2:length(capacitors)

    cap = capacitors(i);

    if strcmp(cap.Package,'0805')
        color = colors(1);
    elseif strcmp(cap.Package,'0603')
        color = colors(2);
    elseif strcmp(cap.Package,'0402')   
        color = colors(3);
    elseif strcmp(cap.Package,'0201')
        color = colors(4);
    end

%     plt = plot(cap.V_Cv,cap.rho_C.*cap.V_Cv.^2,'color',color);
    plt = semilogy(cap.V_Cv,cap.rho_C,'color',color);
    plt.DataTipTemplate.DataTipRows(1).Label = 'Voltage';
    plt.DataTipTemplate.DataTipRows(2).Label = 'Derated Capacitance Per Unit Volume [uF/mm^3]';
    plt.DataTipTemplate.DataTipRows(3).Label = sprintf('Part: %s',cap.Part_Number);
    plt.DataTipTemplate.DataTipRows(4).Label = sprintf('Package: %s',cap.Package);

end

xlabel('Voltage');
ylabel('Derated Capacitance per Unit Volume $[\mu F/mm^3]$');

hold off;

set_figure_style(3);



function [V_Cv,C_Cv,rhoC] = getMurataDeratingCurve(filename,package,C0)

    volume0805 = 2*1.25*1.25; % [mm^3]
    volume0603 = 1.6*0.8*0.8;
    volume0402 = 1*0.5*0.5;   
    volume0201 = 0.6*0.3*0.3;

    data = readmatrix(filename);
    index = find(data(:,1)==0,1,'first');
    data = data(index:end,:);

    V_Cv = data(:,1);
    C_Cv = C0*(1+data(:,2)/100);
    
    if strcmp(package,'0805')
        volume = volume0805;
    elseif strcmp(package,'0603')
        volume = volume0603;
    elseif strcmp(package,'0402')
        volume = volume0402;
    elseif strcmp(package,'0201')
        volume = volume0201;  
    end

    rhoC = C_Cv/volume;

end
