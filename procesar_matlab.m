function procesar_matlab(matFilePath, excelFolder, graficos, escritura, fs, n_channels, ruta_guardado_graficos)
% procesar_matlab  Procesa un .MAT y produce tablas Excel y (opcionalmente) gráficos.
%
%   procesar_matlab(matFilePath, excelFolder, graficos, escritura, fs, n_channels, ruta_guardado_graficos)
%
%   - matFilePath: ruta completa al archivo .mat que contiene la variable `data`.
%   - excelFolder: carpeta donde se guardarán los .xlsx.
%   - graficos:    true para generar gráficos.
%   - escritura:   true para escribir tablas Excel.
%   - fs:          frecuencia de muestreo en Hz.
%   - n_channels:  número de canales (actualmente no usado, pero disponible).
%   - ruta_guardado_graficos: carpeta donde se guardarán los gráficos.

    %— Validaciones iniciales
    assert(isfile(matFilePath), "No existe el .MAT: %s", matFilePath);
    if escritura && ~isfolder(excelFolder)
        mkdir(excelFolder);
    end

    %— Carga del archivo
    S = load(matFilePath);
    assert(isfield(S,'data'), "El .MAT debe contener la variable 'data'");
    u = S.data;

    %— Extraer nombre base (sin extensión)
    [~, name] = fileparts(matFilePath);

    %— Parámetros geométricos
    Da = 2*762/1000; da = 2*350/1000;
    Dc = Da;        dc = 2*101.6/1000;
    A_a = pi*(Da^2 - da^2)/4;
    A_c = pi*(Dc^2 - dc^2)/4;

    %— Señal hidráulica y vector tiempo
    Fza_Hid = (u(:,7)*A_c - u(:,6)*A_a)*(100/5);
    N = size(Fza_Hid,1);
    t = (0:N-1)'/fs;
    t_horas = t / 3600;

    %— Verificar muestras mínimas para rainflow
    if N < 3
        warning("procesar_matlab:insuficienteMuestras", ...
            "'%s' tiene sólo %d muestra(s); se omite el análisis rainflow.", name, N);
        fprintf("%s → OMITIDO (menos de 3 muestras)\n", name);
        return;
    end

    %— Conteo rainflow básico
    try
        [c, ~, rmr, ~, idx] = rainflow(Fza_Hid);
    catch ME
        warning("procesar_matlab:rainflowError", ...
            "'%s' — rainflow básico falló: %s", name, ME.message);
        fprintf("%s → OMITIDO (rainflow falló: %s)\n", name, ME.message);
        return;
    end
    t_peaks   = t(idx);
    Fza_peaks = Fza_Hid(idx);

    %— Delta presión y límites
    dP = u(:,7) - u(:,6);
    lim_sup =  0.45;
    lim_inf = -0.45;

    %— Rainflow con muestreo fs
    try
        [cFs, ~, ~, ~, ~] = rainflow(Fza_Hid, fs);
    catch ME
        warning("procesar_matlab:rainflowFsError", ...
            "'%s' — rainflow(fs) falló: %s", name, ME.message);
        cFs = zeros(0, 5);
    end
    To = array2table(cFs, ...
        'VariableNames', {'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]'});


    %— Filtrado ΔK en 3 umbrales
    K = [65.12307378 57.01521195 42.83250569 27.55061352 14.93805445 7.055368592 3.505949635 2.470266626 2.331041354]';
    F = [1782 1560 1337 1114 891 668 446 223 100]';
    pp = spline(F, K);

    dK_thr = [14, 10.5, 7];

    % Preparo variables
    nCols = size(cFs,2);
    if nCols == 0
        nCols = 5; % seguridad (esperamos 5 columnas en cFs: Ciclos,Rango,Media,ti,ts)
    end

    % Si cFs está vacío, genero filas vacías para cada filtro
    filtros = cell(1,3);
    if isempty(cFs)
        for k = 1:3
            filtros{k} = zeros(1, nCols + 1); % fila de ceros con columna extra delta K
        end
    else
        % Vectorizo cálculo de f_i y f_s
        medias = cFs(:,3);
        rangos = cFs(:,2);
        f_i = medias - rangos/2;   % fuerza mínima
        f_s = medias + rangos/2;   % fuerza máxima

        % Evaluar K en f_i y f_s, cuidando f < 0
        k_i = zeros(size(f_i));
        k_s = zeros(size(f_s));

        pos_i = f_i > 0;
        if any(pos_i)
            % Usamos ppval (igual que tu script original). Alternativa: interp1(...,'pchip','extrap')
            k_i(pos_i) = ppval(pp, f_i(pos_i));
        end
        pos_s = f_s > 0;
        if any(pos_s)
            k_s(pos_s) = ppval(pp, f_s(pos_s));
        end

        dK_vals = k_s - k_i; % ΔK para cada ciclo

        % Construyo las tablas filtradas (añadiendo la columna delta K)
        for k = 1:3
            idx_sel = dK_vals >= dK_thr(k);
            sel = [cFs(idx_sel, :) dK_vals(idx_sel)];
            if isempty(sel)
                sel = zeros(1, nCols + 1);
            end
            filtros{k} = sel;
        end
    end

    %— Escritura Excel
    if escritura
        outFile = fullfile(excelFolder, name + ".xlsx");
        writetable(To, outFile, 'Sheet','Conteo Rainflow','Range','A1');
        for k = 1:3
            sheet = sprintf("delta K = %g", dK_thr(k));
            T = array2table(filtros{k}, ...
                'VariableNames', {'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]','delta K'});
            writetable(T, outFile, 'Sheet',sheet,'Range','A1');
        end
    end

    %— Gráficos opcionales
    if graficos
        % Extraer fecha y unidad del nombre del archivo
        parts = split(name, '-');
        date_str = parts{1};
        unit_str = '';
        if numel(parts) > 1
            unit_str = parts{2};
        end

        % Tipos de gráficos a generar
        graph_types = {'Movimientos', 'Potencia', 'Movimiento alabes', 'Fuerza hidraulica'};

        % 1. Movimientos
        hFig = figure('Visible', 'off');
        plot(t_horas, u(:,8));
        title('Movimientos');
        xlabel('Tiempo (horas)');
        ylabel('Contador');
        xlim([0 24]);
        xticks(0:2:24);
        grid on;
        if ~isempty(ruta_guardado_graficos)
            filename = sprintf('%s-%s-%s.png', date_str, unit_str, graph_types{1});
            saveas(hFig, fullfile(ruta_guardado_graficos, filename));
        end
        close(hFig);

        % 2. Potencia
        hFig = figure('Visible', 'off');
        plot(t_horas, u(:,1));
        title('Potencia');
        xlabel('Tiempo (horas)');
        ylabel('Potencia (MW)');
        xlim([0 24]);
        xticks(0:2:24);
        grid on;
        if ~isempty(ruta_guardado_graficos)
            filename = sprintf('%s-%s-%s.png', date_str, unit_str, graph_types{2});
            saveas(hFig, fullfile(ruta_guardado_graficos, filename));
        end
        close(hFig);

        % 3. Movimiento alabes
        Pos = u(:,3)*((37-10)/100);
        hFig = figure('Visible', 'off');
        plot(t_horas, Pos, 'LineWidth', 1.2);
        title('Movimiento alabes');
        xlabel('Tiempo (horas)');
        ylabel('Álabes (°)');
        xlim([0 24]);
        xticks(0:2:24);
        grid on;
        if ~isempty(ruta_guardado_graficos)
            filename = sprintf('%s-%s-%s.png', date_str, unit_str, graph_types{3});
            saveas(hFig, fullfile(ruta_guardado_graficos, filename));
        end
        close(hFig);

        % 4. Fuerza hidraulica
        hFig = figure('Visible', 'off');
        plot(t_horas, Fza_Hid);
        title('Fuerza hidraulica');
        xlabel('Tiempo (horas)');
        ylabel('Fuerza (kN)');
        xlim([0 24]);
        xticks(0:2:24);
        grid on;
        if ~isempty(ruta_guardado_graficos)
            filename = sprintf('%s-%s-%s.png', date_str, unit_str, graph_types{4});
            saveas(hFig, fullfile(ruta_guardado_graficos, filename));
        end
        close(hFig);
    end

    %— Mensaje final
    fprintf("%s → FINALIZADO\n", name);
end
