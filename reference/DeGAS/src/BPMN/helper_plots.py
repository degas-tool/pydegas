import torch
import matplotlib.pyplot as plt

def evaluate_marginal(output_dist, var_name, x_min, x_max, num_points=1000):
    """Evaluate marginal pdf pointwise to avoid shape mismatch issues."""
    idx = output_dist.var_list.index(var_name)
    xs = torch.linspace(x_min, x_max, num_points)

    pdf_vals = []
    for x in xs:
        # x needs to be shaped like your working call
        val = output_dist.gm.marg_pdf(x.unsqueeze(0), idx)
        pdf_vals.append(val.item())

    return xs, torch.tensor(pdf_vals)


def plot_grid_marginals(output_dist, var_names, x_min=0.0, x_max=20.0, num_points=1000):
    """Plot multiple marginal PDFs in a 3x2 grid."""
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    axes = axes.flatten()

    for i, var_name in enumerate(var_names):
        xs, pdf = evaluate_marginal(output_dist, var_name, x_min, x_max, num_points)

        ax = axes[i]
        ax.plot(xs.numpy(), pdf.numpy())
        ax.set_title(f"PDF of {var_name}")
        ax.set_xlabel(var_name)
        ax.set_ylabel("pdf")
        ax.grid(True)

    plt.tight_layout()
    plt.show()

def plot_pdf_with_histograms(
    output_dist,
    clean_durations,
    x_min=0.0,
    x_max=20.0,
    num_points=100
):

    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    axes = axes.flatten()

    # ------------------------------------
    # Variable names for the 5 activities
    # ------------------------------------
    variable_names = [
        "tactivities[0]",
        "tactivities[1]",
        "tactivities[2]",   
        "tactivities[3]",
        "tactivities[4]",
        "t"
    ]

    # ------------------------------------
    # Plot each variable
    # ------------------------------------
    for plot_idx, var_name in enumerate(variable_names):

        ax = axes[plot_idx]

        # PDF
        xs, pdf = evaluate_marginal(output_dist, var_name, x_min, x_max, num_points)
        ax.plot(xs.numpy(), pdf.numpy(), label="PDF")
        if var_name != "t":
            # Histogram (clean_durations contains NO None now)
            vals = [run[plot_idx] for run in clean_durations if run[plot_idx] is not None]

            ax.hist(vals, bins=30, density=True, alpha=0.4)
        ax.set_title(var_name)
        ax.grid(True)

    # Empty last cell
    axes[-1].axis("off")

    plt.tight_layout()
    plt.show()

